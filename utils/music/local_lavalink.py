# -*- coding: utf-8 -*-
import glob
import os
import platform
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
from contextlib import suppress

import requests
import ruamel.yaml

# youtube-source（Lavalinkのyoutube-plugin）の既定バージョン。
# YouTube側の仕様変更で古いバージョンは再生できなくなるため、application.ymlに
# 記載されているバージョンが古い場合は起動時にこのバージョンへ書き換える。
DEFAULT_YOUTUBE_PLUGIN_VERSION = "1.18.2"

YOUTUBE_PLUGIN_DEPENDENCY_PREFIX = "dev.lavalink.youtube:youtube-plugin:"

# youtube-sourceから削除されたクライアント（そのまま残すと読み込みに失敗する）と、
# 代わりに使用するクライアント。
REMOVED_YOUTUBE_CLIENTS = {
    "TVHTML5EMBEDDED": "TVHTML5_SIMPLY",
}

DEFAULT_YOUTUBE_CLIENTS = ["MUSIC", "ANDROID_VR", "WEB", "WEBEMBEDDED", "TVHTML5_SIMPLY"]

DEFAULT_YOUTUBE_CLIENT_OPTIONS = {
    "TVHTML5_SIMPLY": {"playback": True, "playlistLoading": False},
}


def download_file(url, filename):

    if os.path.isfile(filename):
        return

    r = requests.get(url, stream=True)
    total_size = int(r.headers.get('content-length', 0))
    bytes_downloaded = 0
    previows_progress = 0
    start_time = time.time()

    if total_size >= 1024 * 1024:
        total_txt = f"{total_size / (1024 * 1024):.2f} MB"
    else:
        total_txt = f"{total_size / 1024:.2f} KB"

    with open(f"{filename}.tmp", 'wb') as f:

        for data in r.iter_content(chunk_size=2500*1024):
            f.write(data)
            bytes_downloaded += len(data)
            try:
                current_progress = int((bytes_downloaded / total_size) * 100)
            except ZeroDivisionError:
                current_progress = 0

            if current_progress != previows_progress:
                previows_progress = current_progress
                time_elapsed = time.time() - start_time
                try:
                    download_speed = bytes_downloaded / time_elapsed / 1024
                    if download_speed >= 1:
                        download_speed = (download_speed or 1) / 1024
                        speed_txt = "MB/s"
                    else:
                        speed_txt = "KB/s"
                    print(f"Download do arquivo {filename} {current_progress}% concluído ({download_speed:.2f} {speed_txt} / {total_txt})")
                except:
                    print(f"Download do arquivo {filename} {current_progress}% concluído")

    r.close()

    os.rename(f"{filename}.tmp", filename)

    return True

def validate_java(cmd: str, debug: bool = False):
    try:
        java_info = subprocess.check_output(f"{cmd} -version", stderr=subprocess.STDOUT, text=True, shell=True)
        if int(java_info.splitlines()[0].split()[2].strip('"').split('.')[0]) >= 17:
            return cmd
    except Exception as e:
        if debug:
            print(f"\nFalha ao obter versão do java...\n"
                  f"Path: {cmd} | Erro: {repr(e)}\n")

def is_snapshot_version(version: str):
    # リリース版は 1.18.2 のような数値のみ。それ以外（コミットハッシュ等）はスナップショット扱い。
    return not re.fullmatch(r"\d+(\.\d+)+", version)


def restore_youtube_credentials(yml_data: dict):
    """application.ymlを再ダウンロードした際に、旧ファイルのYouTube認証情報
    （oauthのrefreshTokenとpoToken）を引き継ぐ。"""

    if not os.path.isfile("./application.yml.old"):
        return False

    changed = False

    try:
        yaml = ruamel.yaml.YAML()
        yaml.preserve_quotes = True

        with open("./application.yml.old", "r", encoding="utf-8") as f:
            old_data = yaml.load(f.read()) or {}

        old_youtube = (old_data.get("plugins") or {}).get("youtube") or {}

        for key in ("oauth", "pot"):

            old_value = old_youtube.get(key)

            if not old_value:
                continue

            # 値が未設定（空文字のみ）の場合は引き継がない。
            if not any(v for k, v in old_value.items() if k in ("refreshToken", "token", "visitorData")):
                continue

            yml_data.setdefault("plugins", {}).setdefault("youtube", {})[key] = old_value
            changed = True
            print(f"🌋 - 旧application.ymlからYouTubeの設定を引き継ぎました: plugins.youtube.{key}")

    except Exception as e:
        print(f"⚠️ - 旧application.ymlからのYouTube設定の引き継ぎに失敗しました: {repr(e)}")

    with suppress(OSError):
        os.remove("./application.yml.old")

    return changed


def update_youtube_plugin(youtube_plugin_version: str = None):
    """application.yml内のyoutube-source（youtube-plugin）を指定バージョンへ更新し、
    youtube-sourceから削除された古いクライアント名を修正する。

    変更があった場合はTrueを返す（pluginsフォルダ内の旧jarを削除する必要がある）。
    """

    if not os.path.isfile("./application.yml"):
        return False

    version = (youtube_plugin_version or DEFAULT_YOUTUBE_PLUGIN_VERSION).strip()

    if version.lower() in ("keep", "manual", "disabled", "false"):
        # 手動でバージョンを固定したい場合は自動更新を行わない。
        return False

    if not version or version.lower() in ("auto", "latest", "default", "true"):
        version = DEFAULT_YOUTUBE_PLUGIN_VERSION

    try:
        yaml = ruamel.yaml.YAML()
        yaml.preserve_quotes = True

        with open("./application.yml", "r", encoding="utf-8") as f:
            yml_data = yaml.load(f.read())

        if not yml_data:
            return False

        changed = restore_youtube_credentials(yml_data)
        plugin_changed = False

        dependency = f"{YOUTUBE_PLUGIN_DEPENDENCY_PREFIX}{version}"

        plugins_list = (yml_data.get("lavalink") or {}).get("plugins")

        if plugins_list is None:
            plugins_list = []
            yml_data.setdefault("lavalink", {})["plugins"] = plugins_list

        current = None

        for plugin in plugins_list:
            if str(plugin.get("dependency", "")).startswith(YOUTUBE_PLUGIN_DEPENDENCY_PREFIX):
                current = plugin
                break

        if current is None:
            plugins_list.append({"dependency": dependency, "snapshot": is_snapshot_version(version)})
            plugin_changed = True
        elif current.get("dependency") != dependency:
            print(f"🌋 - youtube-sourceプラグインを更新します: "
                  f"{current.get('dependency')} -> {dependency}")
            current["dependency"] = dependency
            current["snapshot"] = is_snapshot_version(version)
            plugin_changed = True

        youtube_config = (yml_data.get("plugins") or {}).get("youtube")

        if youtube_config is not None:

            clients = youtube_config.get("clients")

            if clients:

                new_clients = []
                clients_changed = False

                for client in clients:
                    replacement = REMOVED_YOUTUBE_CLIENTS.get(str(client).upper())
                    if replacement:
                        print(f"🌋 - application.yml: 廃止されたYouTubeクライアント {client} を "
                              f"{replacement} に置き換えました。")
                        client = replacement
                        clients_changed = True
                    if client not in new_clients:
                        new_clients.append(client)

                if clients_changed:
                    clients[:] = new_clients
                    changed = True

            else:
                youtube_config["clients"] = list(DEFAULT_YOUTUBE_CLIENTS)
                changed = True

            oauth = youtube_config.get("oauth")

            if oauth is not None and oauth.get("enabled") and \
                    not str(oauth.get("refreshToken") or "").strip():
                # refreshTokenが空のままoauthを有効にすると、youtube-sourceが
                # デバイス認証のポーリングスレッドを起動し、HTTP 400を受け取るたびに
                # 待機なしで再試行し続ける（pollForToken内のcatch節にsleepが無い）。
                # YouTubeへ失敗リクエストを投げ続けてIPが制限される原因になるうえ、
                # 連携が完了していないので再生の役にも立たないため無効化する。
                oauth["enabled"] = False
                oauth["skipInitialization"] = True
                changed = True
                print("🌋 - application.yml: refreshTokenが未設定のため、YouTubeのoauth連携を無効化しました "
                      "（連携する場合はオーナー用コマンド ytoauth を使用してください）。")

            client_options = youtube_config.get("clientOptions")

            if client_options is not None:
                for client in list(client_options):
                    if str(client).upper() in REMOVED_YOUTUBE_CLIENTS:
                        del client_options[client]
                        changed = True

                for client, options in DEFAULT_YOUTUBE_CLIENT_OPTIONS.items():
                    if client in youtube_config.get("clients", []) and client not in client_options:
                        client_options[client] = dict(options)
                        changed = True

        if changed or plugin_changed:
            with open("./application.yml", "w", encoding="utf-8") as f:
                yaml.dump(yml_data, f)

    except Exception as e:
        print(f"⚠️ - application.ymlのyoutube-source設定の更新に失敗しました: {repr(e)}")
        return False

    return plugin_changed


def clear_youtube_plugin_jars():
    for filepath in glob.glob("./plugins/youtube-plugin*.jar"):
        try:
            os.remove(filepath)
            print(f"🌋 - 旧youtube-sourceプラグインを削除しました: {filepath}")
        except Exception as e:
            print(f"⚠️ - 旧youtube-sourceプラグインの削除に失敗しました ({filepath}): {repr(e)}")


def run_lavalink(
        lavalink_file_url: str = None,
        lavalink_initial_ram: int = 30,
        lavalink_ram_limit: int = 100,
        lavalink_additional_sleep: int = 0,
        lavalink_cpu_cores: int = 1,
        use_jabba: bool = False,
        youtube_plugin_version: str = None
):
    arch, osname = platform.architecture()
    jdk_platform = f"{platform.system()}-{arch}-{osname}"

    tmp_dir = tempfile.gettempdir() if os.name == "nt" else "."

    if not (java_cmd := validate_java("java")):

        dirs = []

        try:
            dirs.append(os.path.join(os.environ["JAVA_HOME"] + "bin/java"))
        except KeyError:
            pass

        if os.name == "nt":
            dirs.append(f"{tmp_dir}/.java/{jdk_platform}/bin/java")
            try:
                shutil.rmtree("./.jabba")
            except:
                pass

        else:
            if use_jabba:
                dirs.extend(
                    [
                        os.path.realpath("./.jabba/jdk/zulu@1.17.0-0/bin/java"),
                        os.path.expanduser("./.jabba/jdk/zulu@1.17.0-0/bin/java")
                    ]
                )
                try:
                    shutil.rmtree(f"{tmp_dir}/.java")
                except:
                    pass

            else:
                dirs.append(os.path.realpath(f"{tmp_dir}/.java/{jdk_platform}/bin/java"))
                try:
                    shutil.rmtree("./.jabba")
                except:
                    pass

        for cmd in dirs:
            if validate_java(cmd):
                java_cmd = cmd
                break

        if not java_cmd:

            if os.name == "nt":

                try:
                    shutil.rmtree(f"{tmp_dir}/.java")
                except:
                    pass

                if platform.architecture()[0] == "64bit":
                    jdk_url = "https://download.bell-sw.com/java/17.0.13+12/bellsoft-jdk17.0.13+12-windows-amd64.zip"
                else:
                    jdk_url = "https://download.bell-sw.com/java/17.0.13+12/bellsoft-jdk17.0.13+12-windows-i586.zip"

                jdk_filename = "java.zip"

                download_file(jdk_url, f"{tmp_dir}/{jdk_filename}")

                os.makedirs(f"{tmp_dir}/.java/{jdk_platform}", exist_ok=True)

                with zipfile.ZipFile(os.path.normpath(f"{tmp_dir}/{jdk_filename}"), 'r') as zip_ref:
                    try:
                        zip_ref.extractall(f"{tmp_dir}/.java")
                    except Exception as e:
                        if isinstance(e, zipfile.BadZipFile):
                            os.remove(f"{tmp_dir}/{jdk_filename}")
                        raise e

                extracted_folder = None

                java_dirs = os.listdir(f"{tmp_dir}/.java")

                for d in os.listdir(f"{tmp_dir}/.java"):
                    if d == jdk_platform:
                        continue
                    if os.path.isfile(f"{tmp_dir}/.java/{d}/bin/java.exe"):
                        extracted_folder = f"{tmp_dir}/.java/{d}"

                if not extracted_folder:
                    raise Exception(
                        f"JDK não encontrando no diretório: {tmp_dir}/.java\n" + "\n".join(java_dirs)
                    )

                for item in os.listdir(extracted_folder):
                    item_path = os.path.join(extracted_folder, item)
                    dest_path = os.path.join(f"{tmp_dir}/.java/{jdk_platform}", item)
                    os.rename(item_path, dest_path)

                with suppress(FileNotFoundError):
                    os.remove(f"{tmp_dir}/{jdk_filename}")
                with suppress(AttributeError):
                    shutil.rmtree(extracted_folder)

                java_cmd = os.path.realpath(f"{tmp_dir}/.java/{jdk_platform}/bin/java")

            elif use_jabba:

                try:
                    shutil.rmtree("./.jabba/jdk/zulu@1.17.0-0")
                except:
                    pass

                download_file("https://raw.githubusercontent.com/shyiko/jabba/master/install.sh", "install_jabba.sh")
                subprocess.call("bash install_jabba.sh", shell=True)
                subprocess.call("./.jabba/bin/jabba install zulu@1.17.0-0", shell=True)
                os.remove("install_jabba.sh")

                java_cmd = os.path.expanduser("./.jabba/jdk/zulu@1.17.0-0/bin/java")

            else:
                if not os.path.isdir(f"{tmp_dir}/.java/{jdk_platform}"):

                    try:
                        shutil.rmtree(f"{tmp_dir}/.java")
                    except:
                        pass

                    if platform.architecture()[0] != "64bit":
                        jdk_url = "https://download.bell-sw.com/java/21.0.3+12/bellsoft-jdk21.0.3+12-linux-i586-lite.tar.gz"
                    else:
                        jdk_url = "https://download.bell-sw.com/java/21.0.3+12/bellsoft-jdk21.0.3+12-linux-amd64-lite.tar.gz"

                    java_cmd = os.path.realpath(f"{tmp_dir}/.java/{jdk_platform}/bin/java")

                    jdk_filename = "java.tar.gz"

                    download_file(jdk_url, jdk_filename)

                    try:
                        shutil.rmtree(f"{tmp_dir}/.java")
                    except:
                        pass

                    os.makedirs(f"{tmp_dir}/.java/{jdk_platform}")

                    p = subprocess.Popen(["tar", "--strip-components=1", "-zxvf", "java.tar.gz", "-C", f"{tmp_dir}/.java/{jdk_platform}"])
                    p.wait()
                    os.remove(f"./{jdk_filename}")

                else:
                    java_cmd = os.path.realpath(f"{tmp_dir}/.java/{jdk_platform}/bin/java")

    clear_plugins = False

    for filename, url in (
        ("Lavalink.jar", lavalink_file_url),
        ("application.yml", "https://github.com/zRitsu/LL-binaries/releases/download/0.0.1/application.yml")
    ):
        if download_file(url, filename):
            clear_plugins = True

    if update_youtube_plugin(youtube_plugin_version) and not clear_plugins:
        # youtube-sourceのバージョンが変わった場合は、Lavalinkが新しいバージョンを
        # ダウンロードするように旧jarを削除する。
        clear_youtube_plugin_jars()

    if lavalink_cpu_cores >= 1:
        java_cmd += f" -XX:ActiveProcessorCount={lavalink_cpu_cores}"

    if lavalink_ram_limit > 10:
        java_cmd += f" -Xmx{lavalink_ram_limit}m"

    if 0 < lavalink_initial_ram < lavalink_ram_limit:
        java_cmd += f" -Xms{lavalink_ram_limit}m"

    if os.name != "nt":

        if os.path.isdir("./.tempjar"):
            shutil.rmtree("./.tempjar")

        os.makedirs("./.tempjar/undertow-docbase.80.2258596138812103750")

        java_cmd += f" -Djava.io.tmpdir={os.getcwd()}/.tempjar"

    if clear_plugins:
        try:
            shutil.rmtree("./plugins")
        except:
            pass

    java_cmd += " -jar Lavalink.jar"

    print("🌋 - Iniciando o servidor Lavalink (dependendo da hospedagem o lavalink pode demorar iniciar, "
          "o que pode ocorrer falhas em algumas tentativas de conexão até ele iniciar totalmente).")

    lavalink_process = subprocess.Popen(java_cmd.split(), stdout=subprocess.DEVNULL)

    if lavalink_additional_sleep:
        print(f"🕙 - Aguarde {lavalink_additional_sleep} segundos...")
        time.sleep(lavalink_additional_sleep)

    return lavalink_process

if __name__ == "__main__":
    run_lavalink()
    time.sleep(1200)
