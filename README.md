# JP-MuseHeart-MusicBot

## Pythonで作成された音楽ボット 🎵

インタラクティブプレイヤー、スラッシュコマンド対応、[Last.fm](https://www.last.fm/)連携など、多機能なDiscord音楽ボットです。

> **📌 オリジナルリポジトリ**: このプロジェクトは [zRitsu/MuseHeart-MusicBot](https://github.com/zRitsu/MuseHeart-MusicBot) の日本語フォークです。
> 設定ファイル（`.example.env`）のコメントを日本語化しています（一部翻訳中）。

---

## ✨ 主な機能

- 🎮 **インタラクティブプレイヤー** - ボタン操作で簡単に音楽をコントロール
- ⚡ **スラッシュコマンド対応** - モダンなDiscordコマンドに完全対応
- 🎧 **Last.fm連携** - Scrobble機能で再生履歴を記録
- 🎨 **カスタマイズ可能なスキン** - プレイヤーの見た目を自由に変更
- 📢 **RPC (Rich Presence) 対応** - Discordステータスに再生中の曲を表示
- 🔊 **マルチボイスチャンネル対応** - 複数のボイスチャンネルで同時再生可能
- 📝 **Song Requestチャンネル** - 専用チャンネルでリクエスト管理
- 💓 **Uptime Kuma 監視対応** - Push モニターでボットの死活監視が可能
- 🔄 **YouTube再生プラグインの自動更新** - 起動時に youtube-source を指定バージョンへ追従

---

## 📸 プレビュー

### プレイヤーコントローラー（通常モード/ミニプレイヤー）

[![](https://i.ibb.co/6tVbfFH/image.png)](https://i.ibb.co/6tVbfFH/image.png)

<details>
<summary>
🖼️ その他のプレビュー
</summary>
<br>

### スラッシュコマンド

[![](https://i.ibb.co/nmhYWrK/muse-heart-slashcommands.png)](https://i.ibb.co/nmhYWrK/muse-heart-slashcommands.png)

### Last.fm連携

[![](https://i.ibb.co/SXm608z/muse-heart-lastfm.png)](https://i.ibb.co/SXm608z/muse-heart-lastfm.png)

### 固定/拡張モード（Song Requestチャンネル付き）

`/setup` コマンドで設定可能

[![](https://i.ibb.co/5cZ7JGs/image.png)](https://i.ibb.co/5cZ7JGs/image.png)

### フォーラム形式のSong Requestチャンネル

[![](https://i.ibb.co/9Hm5cyG/playercontrollerforum.png)](https://i.ibb.co/9Hm5cyG/playercontrollerforum.png)

💡 `/change_skin` コマンドで様々なスキンを選択できます。[skins](utils/music/skins/) フォルダのテンプレートを参考に、オリジナルスキンを作成することも可能です。

</details>

---

## 🚀 セットアップ手順

### ローカル環境（Windows/Linux）での実行

#### 必要要件

| 要件 | 説明 |
|------|------|
| **Python** | 3.9, 3.10, または 3.11 ([Microsoft Store](https://apps.microsoft.com/store/detail/9PJPW5LDXLZ5) / [公式サイト](https://www.python.org/downloads/)) |
| **Git** | [ダウンロード](https://git-scm.com/downloads)（ポータブル版は不可） |
| **JDK 17以上** | [ダウンロード](https://www.azul.com/downloads)（Windows/Linuxは自動ダウンロード） |

> ⚠️ **システム要件**: 最低 512MB RAM、1GHz CPU（Lavalinkを同じインスタンスで実行する場合）

#### クイックスタート

**1. ソースコードの取得**

```shell
git clone https://github.com/warasugitewara/JP-MuseHeart-MusicBot.git
cd JP-MuseHeart-MusicBot
```

または [ZIPファイル](https://github.com/warasugitewara/JP-MuseHeart-MusicBot/archive/refs/heads/main.zip) をダウンロードして展開

**2. セットアップの実行**

- **Windows**: `source_setup.sh` をダブルクリック
- **Linux**:
```shell
bash source_setup.sh
```

**3. 環境設定**

`.example.env` を `.env` にコピーして編集し、以下の項目を設定：

| 項目 | 説明 |
|------|------|
| `TOKEN` | Discordボットのトークン（必須） |
| `DEFAULT_PREFIX` | コマンドのプレフィックス（デフォルト: `!!`） |
| `MONGO` | MongoDB接続URL（未設定時はJSONファイルで代替） |
| `SPOTIFY_CLIENT_ID` | Spotify Client ID |
| `SPOTIFY_CLIENT_SECRET` | Spotify Client Secret |
| `UPTIME_KUMA_PUSH_URL` | Uptime Kuma Push URL（省略可） |
| `LAVALINK_YOUTUBE_PLUGIN_VERSION` | YouTube再生に使う youtube-source のバージョン（省略可） |

**4. ボットの起動**

- **Windows**: `source_start_windows.bat` をダブルクリック
- **Linux**:
```shell
bash source_start.sh
```

#### 更新方法

```shell
bash source_update.sh
```

> ⚠️ 更新時、手動で行った変更が上書きされる可能性があります

---

## 💓 Uptime Kuma 監視（オプション）

[Uptime Kuma](https://github.com/louislam/uptime-kuma) の Push モニターを使ってボットの死活監視ができます。

**設定手順:**

1. Uptime Kuma で **Push** タイプのモニターを新規作成
2. 表示される Push URL をコピー（例: `https://status.example.com/api/push/xxxxxxxxxx?status=up&msg=OK&ping=`）
3. `.env` に追記:

```env
UPTIME_KUMA_PUSH_URL='https://status.example.com/api/push/xxxxxxxxxx?status=up&msg=OK&ping='
```

4. ボットを再起動

> 💡 モニターのハートビート間隔は **90秒以上** に設定することを推奨します（ボットは60秒ごとに送信します）。

---

## 🎬 YouTube再生について

YouTubeは配信方式やクライアント判定を頻繁に変更するため、再生用プラグイン
（[youtube-source](https://github.com/lavalink-devs/youtube-source)）が古いと再生できなくなります。

このフォークでは、起動時に `application.yml` を自動的に調整します。

- youtube-source の依存関係を `LAVALINK_YOUTUBE_PLUGIN_VERSION` の値へ書き換え、
  バージョンが変わっていれば `plugins/` 内の旧jarを削除して再取得させる
- youtube-source から廃止されたクライアント名を後継のものへ置き換える
- `refreshToken` が空のまま oauth が有効になっている場合は無効化する
  （YouTubeへ失敗リクエストを送り続け、IPが制限される原因になるため）

再生できなくなった場合は、まず `.env` でプラグインのバージョンを上げて再起動してください。

```env
# リリース版を指定する場合
LAVALINK_YOUTUBE_PLUGIN_VERSION='1.18.2'

# mainブランチの修正が必要な場合はコミットハッシュを指定
LAVALINK_YOUTUBE_PLUGIN_VERSION='f45bbb7aebfcbc1c553769e04af6cd43afa8b7c3'
```

数字のみの値はリリース版、それ以外（コミットハッシュ等）はスナップショットとして扱われます。
`keep` を指定すると自動更新を行わず、`application.yml` の内容をそのまま使用します。

> 📌 現在の既定値はmainブランチのコミットハッシュです。最新リリースの 1.18.2 では、
> YouTubeがSABR応答を返す環境で再生できない問題が未修正のためです。詳細は下記のドキュメントを参照してください。

### 関連コマンド（ボットのオーナー専用）

| コマンド | 説明 |
|---|---|
| `ytpotoken` | poToken を設定（`Sign in to confirm you're not a bot` が出る場合） |
| `ytoauth` | Googleアカウントを連携して `TV` クライアントを有効化 |
| `ull` | Lavalink.jar を更新して再起動（`-yml` で application.yml も再取得） |
| `rll` | ローカルLavalinkを再起動 |

> ⚠️ `ytoauth` はGoogleアカウントがBANされる可能性があります。
> メインのアカウントではなく、使い捨てアカウントを使用してください。

**再生できない場合の調査手順と過去の事例は
[YouTube再生のトラブルシューティング](docs/youtube-playback-troubleshooting.md) にまとめています。**

---

## ⚠️ 注意事項

### 使用について

- このソースコードは、プライベート使用または自分が管理するサーバーでの使用を想定しています
- 大規模な公開ボットとしての使用は、最適化の観点から推奨されません
- 公開配布する場合は、元の[ライセンス](/LICENSE)に従う必要があります

### カスタマイズについて

- ソースコードの変更には、Python、disnake、Lavalinkの知識が必要です
- 変更を加えた場合のサポートは提供されません（カスタムスキンを除く）
- 更新時に変更が失われる可能性があります

### 問題報告

YouTubeが再生できない場合は、先に
[YouTube再生のトラブルシューティング](docs/youtube-playback-troubleshooting.md) を確認してください。

このフォーク固有の問題は [Issue](https://github.com/warasugitewara/JP-MuseHeart-MusicBot/issues) で報告してください。
オリジナルボットの不具合は [zRitsu/MuseHeart-MusicBot](https://github.com/zRitsu/MuseHeart-MusicBot/issues) へ。

---

## 📜 ライセンス

このプロジェクトは元のリポジトリの[ライセンス](/LICENSE)に従います。

---

## 🙏 クレジット・謝辞

### このフォークの著者

- **[warasugitewara](https://github.com/warasugitewara)** - 日本語化・Uptime Kuma対応
- **[@claude](https://github.com/claude)** (Anthropic) - 実装支援

### オリジナル開発者

- **[zRitsu](https://github.com/zRitsu)** - MuseHeart-MusicBot オリジナル作者

### 使用ライブラリ・プロジェクト

- [DisnakeDev](https://github.com/DisnakeDev) - disnake
- [Rapptz](https://github.com/Rapptz/discord.py) - discord.py
- [Pythonista Guild](https://github.com/PythonistaGuild) - wavelink
- [Lavalink-Devs](https://github.com/lavalink-devs) - Lavalink & Lavaplayer
- [DarrenOfficial](https://lavalink-list.darrennathanael.com/) - Lavalink サーバーリスト
- [louislam](https://github.com/louislam/uptime-kuma) - Uptime Kuma
