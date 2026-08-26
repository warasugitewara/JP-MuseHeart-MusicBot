# YouTube再生のトラブルシューティング

ローカルLavalink（`LOCAL` ノード）でYouTubeの曲が再生できない場合の調査手順と、
2026年8月に実際に発生した事例の記録です。

---

## 1. 症状

YouTubeの曲を再生しようとすると、プレイヤーに次の警告が表示され、再生されない。

> サーバー `LOCAL` でのYouTube制限のため、現在のセッション中はキュー内のYouTube曲の名前を使用して
> 他の音楽プラットフォームから同じ曲を取得しようとします。

このメッセージは `utils/music/models.py` の `TrackException` ハンドラが出しているもので、
**YouTubeの曲の再生に失敗し、かつ代替できるLavalinkノードが他に無い**ときに表示されます。
つまり「何かに失敗した」という結果だけを伝えるもので、原因そのものは示していません。

---

## 2. 原因の調べ方

### 2-1. 本当の失敗理由はLavalinkのログにある

ボットは `application.yml` の設定でLavalinkのログをファイルに出力しています。

```bash
cd ~/MuseHeart-MusicBot
ls -lt .logs/lavalink/
```

ファイル名は `spring.log` です（`*.log` というglobにはマッチしません）。

**最重要のコマンド** — 各YouTubeクライアントがどう失敗したかが分かります。

```bash
grep -n "Client \[" .logs/lavalink/spring.log | tail -30
```

出力例:

```
Client [ANDROID_VR] failed: This video requires login.
Client [WEB] failed: No supported audio streams available, available types:
Client [WEB_EMBEDDED_PLAYER] failed: Video player configuration error
Client [TVHTML5] failed: The page needs to be reloaded.
Client [TVHTML5_SIMPLY] failed: Sign in to confirm you're not a bot
```

`clients` に登録された各クライアントが順番に試され、すべて失敗すると再生エラーになります。

### 2-2. 失敗理由の読み方

| メッセージ | 意味 | 対処 |
|---|---|---|
| `No supported audio streams available` | **SABR応答**。フォーマットに再生用URLが含まれていない | プラグイン更新 / poToken |
| `Video player configuration error` | 同上（WEBEMBEDDED側の表現） | プラグイン更新 / poToken |
| `Sign in to confirm you're not a bot` | IPに対するボット判定 | poToken / oauth連携 |
| `This video requires login.` | クライアントが古く弾かれている | プラグイン更新 |
| `The page needs to be reloaded.` | `TV` クライアントがoauth未連携 | `ytoauth` で連携、または無視 |

### 2-3. その他の確認コマンド

```bash
# OAuth以外のWARN/ERROR（oauthのログは量が多いので除外する）
grep -inE "WARN|ERROR" .logs/lavalink/spring.log | grep -vi oauth | tail -n 40

# 実際に読み込まれているプラグインのバージョン
grep -n "youtube-plugin" application.yml
ls -la plugins/

# 起動時にapplication.ymlがどう書き換えられたか
journalctl -u music-bot.service -b --no-pager | grep -E "youtube-source|application.yml"

# Javaが実際に使っている通信経路（IPv4かIPv6か）
sudo ss -tnp state established | grep -i java
```

> `[::ffff:192.168.1.10]` のような表記はIPv4射影アドレスであり、IPv4での通信です。
> `curl` はRFC 6724に従いIPv6を優先しますが、JVMは `java.net.preferIPv6Addresses` の
> 既定値が `false` のため、デュアルスタック環境ではIPv4を先に試します。
> `curl` の結果だけを見てIPv6が原因だと判断しないでください。

---

## 3. 2026年8月に発生した事例の記録

「YouTubeが再生できない」という一つの症状の裏に、**独立した4つの原因**がありました。

### 原因1: 古いyoutube-sourceプラグインが更新されない

`application.yml` は zRitsu/LL-binaries から取得しますが、
`utils/music/local_lavalink.py` の `download_file()` は
**ファイルが既に存在するとダウンロードをスキップ**します。

そのため `application.yml` に固定された youtube-source のスナップショット
（`023666c...` / 2026年1月・1.17.0相当）が更新されず、
`ull` コマンドでLavalink.jarを更新しても、Lavalinkは毎回同じ古いプラグインを取得し直していました。
これが「入れ直しても直らない」の正体です。

加えて、`clients` / `clientOptions` に youtube-source から削除済みの
`TVHTML5EMBEDDED` が残っていました。

**対処**: 起動時に `application.yml` の youtube-plugin の依存関係を
`LAVALINK_YOUTUBE_PLUGIN_VERSION` の値へ自動的に書き換え、
バージョンが変わった場合は `plugins/` 内の旧jarを削除するようにしました。
廃止された `TVHTML5EMBEDDED` は後継の `TVHTML5_SIMPLY` へ自動置換します。

### 原因2: 空のrefreshTokenでoauthが有効になっていた

`plugins.youtube.oauth` が `enabled: true` のまま `refreshToken` が空だと、
youtube-sourceは起動時にデバイス認証フローを開始し、承認されるまでポーリングを続けます。

このときの実装が問題で、`pollForToken()` の `catch` 節には待機処理がありません。

```java
while (true) {
    try {
        JsonBrowser response = fetchRefreshToken(httpInterface, deviceCode);
        ...
    } catch (InterruptedException | RuntimeException e) {
        log.error("Failed to fetch OAuth2 token response", e);   // sleepなしでループ継続
    }
}
```

YouTubeがHTTP 400を返す状況では、`youtube.com/o/oauth2/token` への失敗リクエストを
延々と投げ続けることになります。実際に**1時間で17,900行以上のERRORログ**が出ていました。
連携は完了しないので再生の役に立たない一方、同一IPから大量の失敗リクエストを
送り続けるため、YouTube側の制限を招く原因になります。

**対処**: `refreshToken` が空の場合は起動時に `oauth.enabled: false` へ書き換えます。
`ytoauth` でトークンを設定した場合は何もしません。

### 原因3（本命）: SABR応答

YouTubeが `WEB` / `WEBEMBEDDED` クライアントに対し、
`adaptiveFormats` に `url` も `signatureCipher` も含まず
`serverAbrStreamingUrl`（`sabr=1`）だけを返すようになっていました。
これは SABR（Server-side Adaptive BitRate）と呼ばれる配信方式です。

youtube-source側では、URLを持たないフォーマットはすべて捨てられます。

```java
// StreamingNonMusicClient.extractFormat
if (DataFormatTools.isNullOrEmpty(url) && DataFormatTools.isNullOrEmpty(cipherInfo.get("url"))) {
    log.debug("Client '{}' is missing format URL for itag '{}'. SABR response?", ...);
    return false;
}
```

結果、再生可能なフォーマットが1つも残らず失敗します。

当時の最新リリース 1.18.2（2026-07-27）にはこの状況で使える再生手段がなく、
mainブランチに以下の修正が入っていました（いずれも2026-08-19〜20）。

| コミット | 内容 |
|---|---|
| `6579cdf` | IOSのクライアントバージョンを 19.45.4 → 21.32.4、`playerParams` を MOBILE → WEB に変更して再生可能に |
| `34ee4c5` | ANDROIDのクライアントバージョン 19.44.38 はInnerTubeから常にHTTP 400を返されるため 21.02.35 へ更新。plain urlを持つprogressive formatが返るようになる |
| `b33460b` | TVクライアントのUser-AgentをPlayStation 4のものへ変更 |
| `f45bbb7` | `contentLength` を持たないフォーマット（itag 18）の全長を復元 |

重要な点として、`1.18.2..main` の差分は
`Android.java` / `Ios.java` / `Tv.java` / `YoutubeAudioTrack.java` の4ファイルのみで、
**`AndroidVr.java` やWEB系のクライアントには変更がありません**。
つまりプラグインを更新するだけでは既存の `ANDROID_VR` の挙動は変わらず、
修正された `ANDROID` / `IOS` は既定の `clients` に登録されていないため、
**プラグインの更新とクライアントの登録の両方**が必要でした。

**対処**: `LAVALINK_YOUTUBE_PLUGIN_VERSION` の既定値を上記4件を含むmainのコミットに変更し、
`clients` に `ANDROID` と `IOS` を再生専用（`playback: true` / `searching: false` /
`playlistLoading: false`）として `ANDROID_VR` の直後に追加するようにしました。
SABRの影響を受ける `WEB` / `WEBEMBEDDED` より先に試されます。

### 原因4: コマンドのエイリアス重複でモジュールが読み込まれない

上記の対応中に混入した不具合です。`ytpotoken` コマンドのエイリアスに
`"potoken"` と `"poToken"` の両方を指定していました。

Botは `case_insensitive=True` で生成されているため、disnakeの `all_commands` は
キーを `casefold()` する `_CaseInsensitiveDict` になり、両者が衝突して
`CommandRegistrationError` が発生します。

`load_modules()` は `bot_ready` がFalseの間、例外を再送出する作りです。

```python
except Exception as e:
    print(f"❌ - {bot_name} - モジュールの読み込み/再読み込みに失敗しました: {filename}")
    if not self.bot_ready:
        raise e
```

これが `initial_setup()` の `try/except Exception` に捕まるため、
以降のモジュール読み込みと `sync_command_cooldowns()` / `sync_app_commands()` /
`add_view()` がすべてスキップされたまま `bot_ready = True` になります。
**Botはオンラインになるのに、コマンドに一切応答しない**という状態でした。

> 💡 Botがオンラインなのに無反応な場合は、まずこれを確認してください。
> ```bash
> journalctl -u music-bot.service -b --no-pager | grep "モジュールの読み込み"
> ```

---

## 4. 今後またYouTubeが再生できなくなったら

### 手順1: youtube-sourceを最新にする

YouTube側の仕様変更に対する修正は、youtube-source側で継続的に行われています。
まずはプラグインのバージョンを上げてください。

`.env` を編集して再起動するだけで、`application.yml` は自動的に書き換わり、
旧jarも削除されて新しいものが取得されます。

```env
# リリース版を使う場合（数字のみの値はリリース版として扱われます）
LAVALINK_YOUTUBE_PLUGIN_VERSION='1.19.0'

# mainブランチの修正が必要な場合はコミットハッシュを指定（スナップショットとして扱われます）
LAVALINK_YOUTUBE_PLUGIN_VERSION='f45bbb7aebfcbc1c553769e04af6cd43afa8b7c3'
```

- リリース一覧: <https://github.com/lavalink-devs/youtube-source/releases>
- `application.yml` を手動管理したい場合は `keep` を指定すると自動更新されません

### 手順2: クライアント構成を見直す

`grep "Client \["` の結果を見て、どのクライアントが生きているか確認します。
新しく再生可能になったクライアントがあれば `application.yml` の `clients` に追加し、
`clientOptions` で `playback: true` にしてください。

クライアントごとの対応状況は youtube-source のREADMEの
「Available Clients」表が一次情報です。

### 手順3: ボット判定を回避する

`Sign in to confirm you're not a bot` が出ている場合はIPがボット判定を受けています。

**poToken**（`WEB` / `WEBEMBEDDED` に効く）

```
<prefix>ytpotoken                        # サーバー上のブラウザで自動取得
<prefix>ytpotoken <poToken> <visitorData>  # 別環境で取得した値を手動指定
```

自動取得にはChromium/Chromeと表示環境が必要です。ヘッドレスのサーバーでは
別のPCで [youtube-trusted-session-generator](https://github.com/iv-org/youtube-trusted-session-generator)
を実行し、得られた値を引数で渡してください。
値は稼働中のLavalinkへ即時適用され、`application.yml` にも保存されます。
poTokenには有効期限があるため、再生できなくなったら再実行してください。

**oauth連携**（`TV` クライアントに効く）

```
<prefix>ytoauth
```

デバイス認証フローなので特別な環境は不要です。表示されたURLとコードを
スマホやPCのブラウザで入力するだけで完了します。

> ⚠️ **BANされる可能性があるため、メインのGoogleアカウントは絶対に使わないでください。**
> 電話番号やリカバリーメールを登録していない使い捨てアカウントを用意してください。

### 手順4: Lavalink本体を更新する

```
<prefix>ull        # Lavalink.jarを更新して再起動
<prefix>ull -yml   # application.ymlも再取得（oauthのrefreshTokenとpoTokenは引き継がれます）
<prefix>rll        # 再起動のみ
```

---

## 5. 既知の未解決問題

### Spotifyのフォールバック検索が失敗する

YouTubeが再生できないとき、ボットは曲名で他プラットフォームを検索しますが、
`spsearch:` が次のエラーで失敗します。

```
ERROR SpotifyTokenTracker : No secret array found in script: https://open.spotifycdn.com/cdn/build/mobile-web-player/...js
ERROR SpotifyTokenTracker : No secret found.
ERROR AudioLoaderRestHandler : Failed to load track for identifier spsearch:...
```

`application.yml` の `plugins.lavasrc.spotify.clientId` / `clientSecret` が空のため、
LavaSrcがSpotifyの匿名トークンをJSから抽出しようとして失敗しています
（Spotify側のバンドル構成の変更によるもの）。

回避策としては `application.yml` に直接Spotifyのクライアント認証情報を書くか、
lavasrc-pluginを新しいバージョンに上げる方法があります。
なお、`.env` の `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` はボット内部の
Spotifyクライアント用で、Lavalink側のLavaSrcには渡されません。

---

## 6. 関連する設定とファイル

| 対象 | 説明 |
|---|---|
| `LAVALINK_YOUTUBE_PLUGIN_VERSION` | youtube-sourceのバージョン。`keep` で自動更新を無効化 |
| `POTOKEN_YTID` | poToken取得時に再生する動画ID |
| `POTOKEN_BROWSER_EXECUTABLE` | Chromium/Chromeの実行ファイルパス |
| `utils/music/local_lavalink.py` | Lavalinkの起動と `application.yml` の自動更新処理 |
| `modules/ll_yt_oauth.py` | `ytoauth` / `ytpotoken` コマンド |
| `modules/legacy_cmds.py` | `ull` / `rll` コマンド |
| `utils/music/models.py` | 再生失敗時のエラー処理とフォールバック |
| `application.yml` | Lavalinkの設定（gitignore対象・自動更新される） |
| `.logs/lavalink/spring.log` | Lavalinkのログ |
