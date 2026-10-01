# リーガル / リファクタリング レビュー報告書

- **対象リポジトリ**: `warasugitewara/JP-MuseHeart-MusicBot`
- **対象コミット**: `327097c` (`fix: /about のソースリンクを実際に動作しているリポジトリへ変更`)
- **レビュー日**: 2026-09-27
- **対象範囲**: Python 59ファイル / 約36,700行（`wavelink/` のベンダリング分を含む）

## 調査方法と検証状況

| 項目 | 方法 |
|---|---|
| 依存ライブラリのライセンス | PyPI / GitHub を実際に取得して確認（後述の各項目に取得日を記載） |
| コード構造メトリクス | `ast` による関数・クラス行数の機械集計 |
| 構文健全性 | 全59ファイルを `py_compile` で検証 → **失敗0件** |
| 秘密情報の混入 | 作業ツリーおよび取得済みコミット履歴を正規表現走査 |

> ⚠️ **履歴走査の限界**: このセッションのクローンは shallow（`git rev-parse --is-shallow-repository` → `true`、取得済み75コミット）です。
> 「履歴に秘密情報なし」という結論は**取得できた範囲**に限ります。全履歴の監査は
> 完全クローンに対して `gitleaks` / `trufflehog` を実行して確認してください。

---

# 第1部: リーガル（ライセンス・法務）レビュー

## 総評

本プロジェクトは **GPL-2.0-only** です。`LICENSE` は GPL-2 本文のみで、ソースのどこにも
"either version 2 ... or (at your option) any later version" の宣言がありません
（`grep -rn "later version"` → LICENSE 以外ヒット0件）。
つまり **GPL-3 / AGPL-3 へアップグレードする余地がなく**、GPL-3系コードとの結合が
一切できない、最も制約の強い状態です。この前提の下で、**配布時にライセンス違反となる
問題が1件（重大）、GPL-2 の手続要件の未充足が3件**見つかりました。

なお本家 `zRitsu/MuseHeart-MusicBot` が GPL-2.0 であることは 2026-09-27 に実取得して確認済みです。
フォークとして GPL-2.0 を継承する方針自体は正当です。

---

## L-1 【重大 / 配布時にライセンス違反】AGPL-3.0 由来コードと AGPL-3.0 ライブラリを GPL-2.0-only プロジェクトに取り込んでいる

**該当箇所**

| ファイル | 内容 |
|---|---|
| `utils/music/youtube_trusted_session_generator.py:1` | `# código original obtido no repositório: https://github.com/iv-org/youtube-trusted-session-generator` |
| `utils/music/youtube_trusted_session_generator.py:7-8` | `import nodriver` / `from nodriver import start, cdp, loop` |
| `requirements.txt:26` | `nodriver==0.32` |
| `requirements.txt:27` | `undetected-chromedriver==3.5.5` |
| `wavelink/node.py:36` | `from utils.music.youtube_trusted_session_generator import Browser`（**モジュールトップレベル**） |

**確認したライセンス**（いずれも 2026-09-27 に実取得）

| 対象 | ライセンス | GPL-2.0-only との関係 |
|---|---|---|
| `iv-org/youtube-trusted-session-generator`（派生元コード） | **AGPL-3.0** | **非互換** |
| `nodriver` (PyPI) | **AGPL-3.0** | **非互換** |
| `undetected-chromedriver` (PyPI) | **GPL-3.0** | **非互換** |

**なぜ「単なる同梱（mere aggregation）」の抗弁が通らないか**

`wavelink/node.py:36` が**トップレベルで** `youtube_trusted_session_generator` を import し、
そのモジュールが**トップレベルで** `nodriver` を import しています。
`wavelink/node.py` は音楽再生の中核モジュールなので、**ボットを起動するだけで AGPL-3.0
ライブラリが必ずロードされます**。オプション機能として切り離されておらず、
単一プロセス・単一 import グラフ内での結合であるため、FSF の解釈でも「1つの著作物」です。

**影響**

1. 現状のままソースを再配布すると、GPL-2.0-only の条件と AGPL-3.0 の条件を同時に満たせず、
   どちらの許諾も成立しません（=著作権侵害）。
2. `youtube_trusted_session_generator.py` 自体は AGPL-3.0 の派生物であり、
   **AGPL-3.0 §13（ネットワーク越し利用者へのソース提供義務）**も本来かかります。
   Discord ボットはネットワークサービスなので、この条項は実質的に効きます。
3. `undetected-chromedriver` は **`requirements.txt` に書かれているだけで、どこからも import
   されていません**（`grep -rn "undetected_chromedriver"` → ヒット0件）。
   使っていないのに GPL-3.0 依存を背負っています。

**推奨対応（優先度順）**

1. **即時**: `requirements.txt:27` の `undetected-chromedriver==3.5.5` を削除する。
   未使用なので機能影響ゼロで GPL-3.0 依存が1つ消えます。
2. **`nodriver` / AGPL コードの扱い** — 以下のいずれかを選択:
   - **(a) 分離する**: `youtube_trusted_session_generator.py` を本体から切り離し、
     別リポジトリ（AGPL-3.0 として明示）の独立した CLI ツールにする。
     本体は「ユーザーが別途取得したツールで生成した poToken を `.env` / `ytpotoken` で
     受け取る」形にし、`wavelink/node.py:36` のトップレベル import を撤去する。
     poToken の手動設定経路（`ytpotoken` コマンド）は既に存在するため、移行コストは小さいはずです。
   - **(b) ライセンスを AGPL-3.0 に上げる** — ただし **本家が GPL-2.0-only のため、これは
     単独ではできません**。本家および全コントリビューターの許諾が必要で、本家が
     更新を止めている状況では現実的ではありません。
   - **(c) `nodriver` を使わない実装に置き換える**（Playwright は Apache-2.0 なので GPL-2 と両立可）。
3. 上記のどれも直ちに採れない場合、**少なくとも README に現状の非互換を明記**し、
   再配布を推奨しない旨を書いてください（違反状態は消えませんが、下流の被害は減ります）。

---

## L-2 GPL-2 §2(a) の「変更の告知」が行われていない

GPL-2 §2(a) は、改変物を配布する際に

> *"cause the modified files to carry prominent notices stating that you changed the files and the date of any change"*

を要求します。本フォークは 40以上のファイルを日本語化し、`utils/uptime_kuma.py` を新規追加、
`utils/music/local_lavalink.py` を大幅改変していますが、**どのファイルにも変更告知がありません**。
`grep -rniE "(copyright|licen[sc]e|SPDX)" --include="*.py"` の結果、
**プロジェクト自身のコードには著作権表示・ライセンスヘッダが1つも存在しません**
（ヒットしたのは `wavelink/`（ベンダリング）と、変数名に "license/limit" を含む偽陽性のみ）。

**推奨対応**

- 各改変ファイルの先頭にヘッダを追加する。最小構成の例:
  ```python
  # SPDX-License-Identifier: GPL-2.0-only
  # Copyright (C) 2025-2026 warasugitewara
  # Copyright (C) zRitsu (original MuseHeart-MusicBot)
  # Modified from zRitsu/MuseHeart-MusicBot: 日本語化・Uptime Kuma 対応・youtube-source 自動更新
  ```
- 全ファイル個別記載が重いなら、`NOTICE` または `CHANGES.md` に
  「本家からの差分の要約と変更時期」をまとめ、README から参照する形でも
  §2(a) の趣旨（下流が「誰が何を変えたか」を追えること）は満たせます。

---

## L-3 `LICENSE` に著作権表示行がない

`LICENSE` は GPL-2 の定型文のみで、GPL-2 が付録で示す
`Copyright (C) <year> <name of author>` の行が**どこにも入っていません**
（`tail -20 LICENSE` は "How to Apply These Terms" の説明文で終わっています）。

これは本家由来の欠落ですが、フォーク側で直せます。GPL の権利行使（差止・ライセンス違反の追及）は
著作権者が特定できて初めて成り立つため、実務上も意味があります。

**推奨対応**: `LICENSE` 冒頭または `NOTICE` に、本家 `zRitsu` と本フォーク `warasugitewara` の
著作権表示を年とともに追記する。

---

## L-4 GPL-2 §3「対応するソース」の提示先が本家を指してしまう設定不整合

GPL-2 §3 は、配布者が**実際に動かしているコードに対応するソース**を提示することを求めます。
`modules/misc.py:653-656` のコメントは、まさにこの点を意識して `/about` のリンクを
`bot.pool.remote_git_url` に変更したと述べています:

```python
# 実際に動作しているコードのリポジトリを指す。本家URLを直接埋め込むと、
# すぐ上に表示している「現在のコミット」のリンク先と食い違ううえ、
# GPL-2が求める「配布物に対応するソース」の提示にもならない。
links = f"[`[ソース]`]({bot.pool.remote_git_url})"
```

**しかし、この修正は `.env` 経由で無効化されます。**

| 箇所 | 値 |
|---|---|
| `config_loader.py:31`（デフォルト） | `https://github.com/warasugitewara/JP-MuseHeart-MusicBot.git` ✅ |
| `.example.env:131`（ユーザーがコピーする側） | `https://github.com/zRitsu/MuseHeart-MusicBot.git` ❌ |

`config_loader.py:192` の `CONFIG.update(dotenv_values())` は**最後に実行される**ため、
`.env` の値がデフォルトを上書きします。README は「`.example.env` を `.env` にコピーして編集」と
指示しているので、**手順どおりに従ったユーザーは全員 `SOURCE_REPO` が本家になります**。

さらに `utils/client.py:673-679` は `git remote -v` の取得に失敗した場合に
`SOURCE_REPO` へフォールバックします。README は ZIP ダウンロードも案内しているため、
**ZIP 展開で動かしている利用者は `/about` の「ソース」が本家を指し、実際に動いている
フォークのコードには到達できません**。GPL-2 §3 の趣旨を満たさない状態です。

**推奨対応**
- `.example.env:131` をフォーク URL に修正する（`config_loader.py:31` と揃える）。1行で直ります。
- 併せて、`.example.env` と `config_loader.py` のデフォルト値が乖離していないかを
  CI で機械的に突き合わせる仕組みを検討してください（同種の乖離は再発しやすい）。

---

## L-5 Google (YouTube TV クライアント) の OAuth 資格情報をハードコードしている

`modules/ll_yt_oauth.py:32-33`

```python
self.client_id = '861556708454-d6dlm3lh05idd8npek18k6be8ba3oc68.apps.googleusercontent.com'
self.client_secret = 'SboVhoG9s0rNafixCSGGKXAT'
```

さらに `get_device_code()` は `device_model: "ytlr::"`（YouTube living-room クライアント）を
送出し、YouTube TV アプリになりすまします。

**論点**

- 第三者（Google）に帰属する OAuth クライアント資格情報を、その用途外で使用しています。
  Google API 利用規約および YouTube API サービス規約に抵触する可能性が高い行為です。
- ユーザーの Google アカウントを、Google が承認していないクライアントとして認可させています。
  README 自身が「`ytoauth` はGoogleアカウントがBANされる可能性があります」と警告しており、
  **リスクの存在は認識されています**。
- 由来はコメントどおり上流の `youtube-source` であり、本フォーク発の問題ではありません。
  ただし**フォークが配布・推奨している**以上、責任は共有されます。

**推奨対応**

- 機能自体の削除は現実的でないと思われるため、**リスク開示の強化**を推奨します。
  現在の README の警告は「使い捨てアカウント推奨」に留まっていますが、
  「Google の利用規約に抵触する可能性があり、アカウント停止の責任は利用者が負う」ことを
  明記してください。
- `ytoauth` の実行時（`YtOauthView` の初回応答）にも同等の警告を出し、
  ユーザーが規約リスクを理解した上で明示同意する導線にすると、法的にも運用的にも安全側です。
- Discord のサーバーメンバーに公開するボットで使う場合、この挙動は
  **オーナー自身のアカウントに限定**されるべきです（現状もオーナー専用コマンドなので
  設計は妥当。README での明示を推奨）。

---

## L-6 YouTube のボット検知回避を目的とした機構

- `utils/music/youtube_trusted_session_generator.py`: ヘッドレス検知を回避するブラウザ自動操作で
  `poToken` / `visitorData` を採取（`nodriver` 使用）
- `requirements.txt`: `yt-dlp`, `curl_cffi`（TLS フィンガープリント偽装に使われる）, `user_agent`
- `docs/youtube-playback-troubleshooting.md` が `Sign in to confirm you're not a bot` 対策を案内

**論点**: YouTube 利用規約は自動化アクセスおよび技術的制限の回避を禁じています。
日本法では私的領域の技術的制限手段回避が直接刑事罰に結びつくケースは限定的ですが、
米国 DMCA §1201 や各国法の下では議論があり、いずれにせよ**規約違反による
アカウント停止・IP 制限のリスクは現実的**です。

**評価**: この種の機能は音楽ボット全般に共通する事情であり、本フォーク固有の落ち度ではありません。
README の「⚠️ 注意事項」に規約リスクを1段落追加すれば、開示としては十分です。

---

## L-7 署名・チェックサムなしの第三者製バイナリを既定でダウンロード・実行する

`config_loader.py:108`

```python
"LAVALINK_FILE_URL": "https://github.com/zRitsu/LL-binaries/releases/download/0.0.1/Lavalink.jar",
```

**評価: 本フォークの対応は適切です。** README に長い注意書きがあり、
`LAVALINK_FILE_SHA256` による検証（`utils/music/local_lavalink.py:73-176`）を
実装済みで、取得時のハッシュを必ずログ出力して固定できるようにしています。
同様に `JABBA_INSTALL_SCRIPT_URL` はコミット固定（`local_lavalink.py:36-39`）されており、
`master` 追従による任意コード実行を避ける配慮がなされています。

**残る指摘（軽微）**

- `LAVALINK_FILE_SHA256` の既定値は空（`config_loader.py:111`）で、**検証はデフォルト無効**です。
  「デフォルト安全」にするなら、既定のハッシュ値を同梱し、
  ユーザーが URL を変えたときだけ空にする運用が望ましいです。
- Lavalink 本体は **MIT ライセンス**（2026-09-27 に実取得して確認）です。
  本リポジトリは jar を**再配布していない**（実行時にダウンロードするだけ）ため、
  MIT の告知義務は本リポジトリには生じません。この点は問題ありません。
  ただし `zRitsu/LL-binaries` が MIT の告知を伴わずに再配布している場合、
  その配布者側に告知義務が生じます。**公式の `lavalink-devs/Lavalink` リリースを
  既定にする**のが、法務・セキュリティ両面で最もクリーンです。

---

## L-8 プライバシーポリシー・利用規約が存在しない

リポジトリに `PRIVACY.md` / `TERMS.md` に相当する文書がありません（`git ls-files` で確認）。

本ボットは以下の個人データを扱います:

| データ | 保存先 |
|---|---|
| Discord ユーザーID / サーバーID / チャンネルID | `utils/db.py`（MongoDB または `database.json`） |
| Last.fm ユーザー名・**セッションキー** | `utils/db.py:66-71` |
| Google アカウントの**メールアドレス**・**refresh token** | `modules/ll_yt_oauth.py:230-233`（MongoDB）、`application.yml` |
| 再生履歴・お気に入り・カスタムプレフィックス | 同上 |
| RPC 経由の「今なにを聴いているか」 | `web_app.py`（メモリ上、WS で配信） |

**論点**

- **Discord Developer Terms of Service / Developer Policy** は、ユーザーデータを収集する
  アプリにプライバシーポリシーの提示を求めています。公開ボットとして運用する場合は必須です。
- 日本の個人情報保護法（APPI）上、Discord ユーザーIDは個人識別符号に該当し得ます。
  EU 利用者がいる場合は GDPR の適用も検討対象です。
- **データ削除の手段が不明**です。GDPR 第17条（消去権）/ APPI の利用停止請求に対応する
  コマンドや手順が見当たりません。

**推奨対応**

- `PRIVACY.md` を追加し、(1) 収集項目、(2) 利用目的、(3) 保存場所と期間、
  (4) 第三者提供（Last.fm / Google / Spotify / Uptime Kuma / エラーレポート Webhook）、
  (5) 削除請求の窓口 を記載する。
- README の「⚠️ 注意事項」は「プライベート使用を想定」と述べていますが、
  公開運用する人は必ず現れます。「公開運用する場合はプライバシーポリシーの整備が必要」と
  1行明記するだけでも、下流の運用者を守れます。

---

## L-9 第三者アカウントの長期資格情報を平文保存している

| 資格情報 | 保存先 | 暗号化 |
|---|---|---|
| Last.fm `sessionkey` | `utils/db.py:71`（既定は `database.json` = 平文JSON） | なし |
| Google `refreshToken` | `modules/ll_yt_oauth.py:230-233`（MongoDB）+ `application.yml` | なし |
| Spotify `access_token` | `utils/music/audio_sources/spotify.py:31` → **`gettempdir()`**（Linux では `/tmp`） | なし |

`.gitignore` により `database.json` / `application.yml` はコミット対象外で、この点は適切です。

**論点**

- Last.fm のセッションキーは**失効しない長期資格情報**で、scrobble / love 操作が可能です。
  漏洩すると当該ユーザーの Last.fm アカウントに第三者が書き込めます。
- `/tmp` は Linux では `1777`（全ユーザー書き込み可）です。デフォルト umask `022` では
  `.spotify_cache.json` が **同一ホストの他ユーザーから読み取り可能**になります。
  共有 VPS / 共用ホスティングでは実害があります。
- `application.yml` に Google の refresh token が平文で入るため、
  バックアップやログの取り扱いに注意が必要です。

**推奨対応**

- `spotify.py:189` の書き込み後に `os.chmod(spotify_cache_file, 0o600)` を追加する（1行）。
  より望ましいのは、キャッシュ先を `gettempdir()` からプロジェクト配下
  （`.spotify_cache.json` は既に `.gitignore` 済み）へ移すことです。
- Last.fm セッションキーと Google refresh token は、`.env` の秘密鍵による対称暗号化
  （例: `cryptography.fernet`）を検討してください。運用負荷とのトレードオフなので、
  少なくとも「平文保存である」ことを `PRIVACY.md` に明記するのが最低線です。

---

## L-10 エラーレポート Webhook が個人データと未マスクのトレースバックを外部送信する

`AUTO_ERROR_REPORT_WEBHOOK` が設定されると、`modules/error_handler.py:415-450` の
`build_report_embed()` が以下を Discord Webhook へ送信します:

- サーバー名 + サーバーID（`error_handler.py:429-432`）
- テキストチャンネル名 + ID（`error_handler.py:434-437`）
- ボイスチャンネル情報（`error_handler.py:439-`）
- コマンド実行者の情報

**加えて、トークンのマスク漏れがあります。**

| 箇所 | 内容 | マスク |
|---|---|---|
| `error_handler.py:117` | ユーザー向け Embed | ✅ `.replace(self.bot.http.token, 'mytoken')` |
| `error_handler.py:255, 263` | 同 | ✅ |
| `modules/music.py:6349` | 同 | ✅ |
| `utils/owner_panel.py:75` | 同 | ✅ |
| **`error_handler.py:150-153`** | **Webhook 添付の完全トレースバック** | ❌ **マスクなし** |
| **`error_handler.py:312-315`** | 同（prefix コマンド経路） | ❌ **マスクなし** |

`string_to_file(full_error_msg, "error_traceback_interaction.txt")` は
`full_error_msg` をそのまま添付します。ユーザー向け表示では一貫してトークンをマスクしている
のに、**外部へ送る完全トレースバックだけがマスクされていません**。
disnake の HTTP 層由来の例外はリクエストヘッダを含み得るため、実害の可能性があります。

**推奨対応**

- `full_error_msg` にも同じマスクを適用する。マスク処理が5箇所に散っているので、
  `utils/others.py` に `redact_token(text: str, bot) -> str` を切り出して
  **全経路から必ず通す**形にリファクタするのが確実です（第2部 R-14 と共通）。
- 既定値が空でオプトインなのは適切ですが、`.example.env` の
  `AUTO_ERROR_REPORT_WEBHOOK` 付近に「サーバー名・チャンネル名が送信される」旨を
  コメントで明記してください。

---

## L-11 README の記述に事実との齟齬がある

事実と異なる記載は、それ自体が法的リスクというより**信頼性と帰属表示の正確性**の問題です。
GPL プロジェクトでは帰属表示の正確さが実務的に重要なので、リーガル項目に含めます。

### (a) 本家のアーカイブ記載 — 「読み取り専用」が現状と異なる

README:

> 📌 本家 zRitsu/MuseHeart-MusicBot は 2026年6月12日にアーカイブされ、読み取り専用になっています。

**確定した事実**（2026-09-27 時点、リポジトリ所有者の確認および実測による）

| 項目 | 確認結果 |
|---|---|
| アーカイブ | 2026年6月12日にアーカイブされたが、**その後アーカイブ解除され、現在は読み取り専用ではない** |
| 本家の最終コミット | **`32f227e` "Include channelId in voice state payload" / 2026-03-02 16:40 -0300**（commits Atom フィードで取得。ローカルの同コミットのコミッタ日時と完全一致） |
| 最終更新からの経過 | 約7ヶ月（アーカイブされる**前**から更新が止まっていた） |

**さらに重要な点: 本フォークは既に本家の HEAD を取り込み済みです。**

```
$ git merge-base --is-ancestor 32f227e main && echo "main に含まれる"
main に含まれる

$ git log -1 --format="%h %ai %s" d5b9f37
d5b9f37 2026-06-06 11:26:24 +0900 Merge branch 'zRitsu:main' into main
```

本家の最終コミット `32f227e` は、2026-06-06 のマージコミット `d5b9f37`
（`Merge branch 'zRitsu:main' into main`）によって本フォークの `main` に取り込まれています。
つまり **2026-09-27 現在、本家から取り込むべき差分は存在しません**。

**README の記述が不正確な点**

1. 「**読み取り専用になっています**」は誤りです。アーカイブは解除されており、
   本家は再び更新可能な状態にあります。
2. アーカイブ日（2026年6月12日）のみを記載し、**最終コミット日（2026-03-02）に触れていない**ため、
   読者は「6月まで開発されていた」と誤解します。実際には3月から更新が止まっています。
3. 「本家の変更を取り込む場合は upstream を追加して手動マージしてください」という案内自体は
   正しいのですが、**現時点では取り込む差分がゼロ**である旨が書かれていないため、
   利用者が不要な作業を行う可能性があります。

**リスク評価の修正**

当初の報告では「誤りであれば上流のセキュリティ修正を取りこぼす」と書きましたが、
**HEAD まで取り込み済みであることが確認できたため、現時点での取りこぼしはありません**。
ただし**アーカイブが解除されている**ということは、**本家が開発を再開し得る**ことを意味します。
「アーカイブされたので追従不要」という前提でフォークを運用すると、
再開時に上流のセキュリティ修正を見落とします。README はこの点を反映すべきです。

**推奨する書き換え**

```markdown
> 📌 本家 [zRitsu/MuseHeart-MusicBot](https://github.com/zRitsu/MuseHeart-MusicBot) は
> 2026年3月2日以降、更新が停止しています（2026年6月12日に一度アーカイブされましたが、
> 現在はアーカイブ解除されています）。
> 本家の最終コミット時点の内容は、このフォークに取り込み済みです（2026年6月6日）。
> 本家が開発を再開した場合は、`upstream` を追加して手動でマージしてください。

> ```shell
> git remote add upstream https://github.com/zRitsu/MuseHeart-MusicBot.git
> git fetch upstream
> git log HEAD..upstream/main --oneline   # 取り込むべき差分があるか確認
> git merge upstream/main
> ```
```

差分確認のための `git log HEAD..upstream/main --oneline` を1行加えておくと、
利用者が「取り込むものがあるか」を自分で判断できます。

### (b) 「一部翻訳中」の記載が古い

README:

> 設定ファイル（`.example.env`）のコメントを日本語化しています（一部翻訳中）。

`.example.env`（376行）をポルトガル語キーワードで走査した結果、**ヒット0件**でした。
翻訳は完了しているため、この括弧書きは削除できます。

### (c) `@claude` (Anthropic) のクレジット

README:

> - **[@claude](https://github.com/claude)** (Anthropic) - 実装支援

- `https://github.com/claude` は Anthropic の公式アカウントではありません。
  第三者アカウントに Anthropic の名前を併記すると、**無関係な個人への誤帰属**になります。
- 「(Anthropic)」の表記は、Anthropic 社が本プロジェクトの開発に関与または
  本プロジェクトを承認しているという誤認を生じさせ得ます（商標・推奨の誤表示）。

**推奨対応**: リンクを外し、社名の併記をやめて、ツール名として記載してください。例:

```markdown
- 実装の一部は Claude Code（AI コーディング支援ツール）を用いて作成しました。
```

### (d) 外部画像ホスティングへの依存

README のプレビュー画像7点すべてが `i.ibb.co`（ImgBB）の直リンクです。
本家由来ですが、**ImgBB のリンクは予告なく失効します**。また第三者ホストの画像を
自リポジトリの README で配信する形になるため、画像の権利関係を自分で管理できません。

**推奨対応**: スクリーンショットを `docs/images/` にコミットし、相対パスで参照する。
GPL-2.0 の下で自プロジェクトの一部として明確に管理できます。

---

## L-12 ベンダリングした `wavelink` のライセンス告知（軽微 / 対応はおおむね良好）

`wavelink/` は PythonistaGuild/Rapptz 由来の MIT ライセンスコードです。

| ファイル | MIT 告知 |
|---|---|
| `client.py`, `eqs.py`, `errors.py`, `events.py`, `node.py`, `player.py`, `stats.py`, `websocket.py` | ✅ ファイル冒頭に MIT 全文 |
| `backoff.py` | ✅ MIT 全文（Copyright 2015-2019 Rapptz） |
| `__init__.py` | ✅ `__license__ = 'MIT'` / `__copyright__ = 'Copyright 2019-2021 (c) PythonistaGuild'` |
| **`meta.py`** | ❌ **告知なし** |

MIT は「上記の著作権表示および許諾表示を、ソフトウェアのすべての複製または
重要な部分に含めること」を求めます。`__init__.py` にパッケージ単位の表示があるため
実務上は許容範囲ですが、`meta.py` にもヘッダを補うのが確実です。

**また、`wavelink/` の各ファイルには「本フォークが改変した」旨の記載がありません。**
実際には Portuguese のログメッセージが追加されており（`node.py:208, 226, 231`、
`player.py:532, 555, 666`）、明らかに上流 0.9.15 からの改変版です。
MIT は改変告知を義務づけませんが、`wavelink/README.md` などに
「PythonistaGuild/Wavelink 0.9.15 を Lavalink v4 対応のため改変」と1文残すと、
下流の混乱（「upstream wavelink のバグだと思って本家に報告する」等）を防げます。

---

## 第1部まとめ

| ID | 深刻度 | 概要 | 修正の重さ |
|---|---|---|---|
| L-1 | **重大** | AGPL-3.0 / GPL-3.0 コードを GPL-2.0-only に取り込み（配布時に違反） | 設計変更（一部は1行） |
| L-4 | **高** | `.example.env` の `SOURCE_REPO` が本家を指し GPL-2 §3 の趣旨を満たさない | **1行** |
| L-2 | 中 | GPL-2 §2(a) の変更告知がない | ヘッダ追加 or `NOTICE` |
| L-3 | 中 | `LICENSE` に著作権表示行がない | 数行 |
| L-8 | 中 | プライバシーポリシーがない（Discord Developer Policy） | 文書追加 |
| L-10 | 中 | Webhook 送信の完全トレースバックがトークン未マスク | 小 |
| L-11(c) | 中 | `@claude` / Anthropic の誤帰属 | 数行 |
| L-5 | 中 | Google TV クライアント資格情報のハードコード（ToS） | 開示強化 |
| L-9 | 中 | 第三者アカウント資格情報の平文保存（`/tmp` 含む） | 小〜中 |
| L-11(a) | 低 | README の「読み取り専用」記載が誤り（アーカイブ解除済み）。最終更新日（2026-03-02）の記載もない。**上流 HEAD は取り込み済みで取りこぼしはなし** | 小 |
| L-6 | 低 | YouTube ボット検知回避（業界共通事情） | 開示のみ |
| L-7 | 低 | 第三者 jar の既定利用（検証機構は実装済み・既定無効） | 小 |
| L-11(b)(d) | 低 | README の陳腐化した記述・外部画像依存 | 小 |
| L-12 | 低 | `wavelink/meta.py` の MIT 告知欠落 | **数行** |

---

# 第2部: リファクタリング / コード品質レビュー

## 総評

`py_compile` は59ファイル全て通り、`config_loader.py` / `utils/music/local_lavalink.py` /
`modules/misc.py:653` などフォークが手を入れた箇所には**「なぜこうしたか」を説明する
質の高い日本語コメント**が残されています。フォーク独自の作業品質は高いと評価できます。

一方で、本家由来の構造的負債がそのまま残っています。機械集計の結果:

| 指標 | 値 |
|---|---|
| 総行数 | 約 36,700行 |
| 関数総数 | 1,010 |
| 100行超の関数 | **72** |
| 200行超の関数 | **29** |
| 500行超の関数 | **3** |
| 最大関数 | `modules/music.py:606 play` = **1,458行** |
| 最大クラス | `modules/music.py:51 Music` = **7,723行** |
| `except:`（裸の except） | **365箇所** |
| うち直後が `pass` / `continue` | **190箇所** |
| テストファイル | **0** |
| CI 設定 (`.github/`) | **なし** |
| リンタ / フォーマッタ設定 | **なし** |

以下、**確定バグ → セキュリティ → 構造** の順に記載します。

---

## 確定バグ

### R-1 【高】Spotify 認証エラー時に `get_access_token()` が永久ハングする

`utils/music/audio_sources/spotify.py:141-190`

```python
async def get_access_token(self):
    if self.token_refresh:
        while self.token_refresh:        # ← ここに落ちると永久ループ
            await asyncio.sleep(1)
        return
    self.token_refresh = True
    try:
        ...
        if data.get("error"):
            self.client_id = None
            self.client_secret = None
            await self.get_access_token()   # 168-170: 再帰。token_refresh は True のまま
            return                          # ← try を抜けるので 187 に到達しない
    except Exception as e:
        self.token_refresh = False          # 184
        raise e
    self.token_refresh = False              # 187: 正常系のみ
```

`self.token_refresh` が `False` に戻るのは **184行（例外時）と 187行（正常時）だけ**です。
168-171 のエラー分岐は `return` で抜けるため、**どちらにも到達しません**。

**再現シナリオ**: `.env` の `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` が誤っている
（失効・タイポ・revoke 済み）

1. `get_access_token()` → `token_refresh = True`
2. Spotify が `error` を返す → 再帰呼び出し
3. 再帰した側は `if self.token_refresh:` が真 → `while self.token_refresh: await asyncio.sleep(1)`
4. **`token_refresh` を `False` にするコードパスが存在しない** → 無限ループ
5. 以降、Spotify リンクを投げた**全ユーザーのコマンドが永久に応答しなくなる**
   （`request()` も `get_valid_access_token()` 経由でここを待つ）

**修正方針**: `try/finally` でフラグを確実に解放し、再帰をやめて明示的に無効化する。

```python
async def get_access_token(self):
    if self.token_refresh:
        while self.token_refresh:
            await asyncio.sleep(1)
        return
    self.token_refresh = True
    try:
        ...
        if data.get("error"):
            print(f"⚠️ - Spotify: トークン取得に失敗しました: {data['error_description']}")
            self.disabled = True       # 再帰せず、Spotify サポートを無効化して抜ける
            return
        ...
    finally:
        self.token_refresh = False     # 全経路で必ず解放
```

**関連（同ファイル）**: `request()` の 401 ハンドリング（`spotify.py:73-75`）も
リトライ回数の上限なしで自己再帰します。トークンが取得できても即 401 が返る状況
（スコープ不正など）では、実 HTTP リクエストを伴う再帰が `RecursionError` まで続きます。
リトライ上限（1回で十分）を入れてください。

---

### R-2 【中】`web_app.py` の `on_close()` が `ValueError` を投げる

`web_app.py:250-280`

```python
def on_close(self):
    if self.user_ids:
        ...
        return
    if not self.bot_ids:
        print(f"接続終了 - IP: {self.request.remote_ip}")
    else:
        ...
    bots_ws.remove(self)        # 280
```

`user_ids` も `bot_ids` も空のまま切断された接続（= WS を開いて何も送らずに閉じた接続）は、
`bots_ws` に `append` されていないのに 280行で `remove` されます
→ **`ValueError: list.remove(x): x not in list`**。

`/ws` に接続して即切断するだけで誰でも到達できます。Tornado がコールバック単位で
例外を捕まえるためプロセスは落ちませんが、ログが汚染され、ポートスキャンや
ヘルスチェックのたびに発生します。

**修正**: `if self in bots_ws: bots_ws.remove(self)` もしくは `with suppress(ValueError):`。

---

### R-3 【中】`modules/ll_yt_oauth.py:259` の `encoding` 指定漏れ — Windows で `application.yml` が壊れる

プロジェクト内で `application.yml` を開いている6箇所のうち、**5箇所は `encoding` を明示し、
1箇所だけ漏れています**:

| 箇所 | 指定 |
|---|---|
| `modules/ll_yt_oauth.py:246` (r) | ✅ `encoding='utf-8'` |
| **`modules/ll_yt_oauth.py:259` (w)** | ❌ **なし** |
| `modules/ll_yt_oauth.py:335` (r) | ✅ |
| `modules/ll_yt_oauth.py:343` (w) | ✅ |
| `utils/music/local_lavalink.py:258` (r) | ✅ |
| `utils/music/local_lavalink.py:374` (w) | ✅ |

`open('./application.yml', 'w')` は `locale.getpreferredencoding()` を使うため、
日本語 Windows では **cp932** になります。

**影響**: `ytoauth` コマンドで Google 連携を行うと、`application.yml` 全体が cp932 で
書き戻されます。ファイル内に cp932 で表現できない文字（他プラグインの設定値、
絵文字、UTF-8 のコメント）があれば `UnicodeEncodeError` で中断し、
そうでなくても以降 `encoding='utf-8'` で読む 246行 / 335行 / `local_lavalink.py:258` が
**`UnicodeDecodeError` で失敗**します。README が Windows を主要プラットフォームとして
案内している以上、実害があります。

**修正**: `open('./application.yml', 'w', encoding='utf-8')` — **1行**。

---

### R-4 【低】`updatelog` コマンドにオーナー制限が抜けている

`modules/legacy_cmds.py:540-543`

```python
@commands.cooldown(1, 10, commands.BucketType.user)
@panel_command(aliases=["latest", "lastupdate"], description="最新のアップデートを表示します。",
               emoji="📈", alt_name="最新のアップデート", hidden=False)
async def updatelog(self, ctx, amount: int = 10):
```

`Owner` cog の他のパネルコマンド（`reloadconfig` :206, `reloadskins` :221, `reload` :243,
`update` :310, `exportsource` :719 …）はすべて `@commands.is_owner()` を持ちますが、
**`updatelog` だけ付いていません**。`cog_check`（:1126）は
`check_requester_channel(ctx)` のみで、オーナー判定をしません。

**影響**: 誰でも `!!updatelog` / `!!latest` で `git log` を実行できます。
リポジトリが public なので情報漏洩の実害は小さいですが、
**任意ユーザーがサブプロセス起動を誘発できる**点と、`hidden=False` で
ヘルプに露出している点で、アクセス制御ポリシーが一貫していません。

なお `amount: int` は disnake のコンバータが整数を強制するため、
**コマンドインジェクションは成立しません**（`git log -{amount}` は文字列連結ですが、
非整数は `BadArgument` で弾かれます）。

**修正**: `@commands.is_owner()` を付けるか、意図的に公開するなら
`run_command` を使わない実装（キャッシュ済みコミット情報の表示）に変える。

---

### R-5 【低】`remote_git_url` のパースが壊れやすい

`utils/client.py:673-674`

```python
self.remote_git_url = check_output(['git', 'remote', '-v']).decode('ascii').strip()\
    .split("\n")[0][7:].replace(".git", "").replace(" (fetch)", "")
```

- `[7:]` は **リモート名が正確に `origin`（6文字）+ タブ = 7文字**であることを前提にしています。
  README は `git remote add upstream ...` を案内しており、`git remote -v` は
  アルファベット順なので現状は `origin` が先に来ますが、
  `fork` や `jp` のような短い名前のリモートを追加すると `[7:]` が URL を切り落とします。
- `.replace(".git", "")` は文字列中のどこでも置換するため、
  `github.com/foo/my.gitlab-mirror` のような URL を破壊します。
- `.decode('ascii')` は非 ASCII を含むリモート URL で `UnicodeDecodeError` になります。

**修正**: `git remote get-url origin` を使い、末尾のみ除去する。

```python
url = check_output(['git', 'remote', 'get-url', 'origin']).decode('utf-8').strip()
self.remote_git_url = url[:-4] if url.endswith('.git') else url
```

（末尾 `.git` の除去は `utils/client.py:683-684` に既に正しい実装があるので、そちらへ寄せる。）

---

## セキュリティ

### R-6 【高】RPC WebSocket サーバーに認証がなく、全ユーザーの再生情報を取得できる

`web_app.py` の `WebSocketHandler` には以下の問題が重なっています。

#### (a) 「ボット」を自称するだけで全ユーザーの RPC データを受信できる

`web_app.py:199-204`

```python
is_bot = data.pop("bot", False)

if is_bot:
    print(f"🤖 - 新しい接続 - Bot: {ws_id} {self.request.remote_ip}")
    self.bot_ids = ws_id
    bots_ws.append(self)
    return
```

**クライアントが送ってきた `bot: true` を無検証で信用**しています。
`{"user_ids": [1], "bot": true}` を送るだけで `bots_ws` に登録され、以降
`web_app.py:238-244` により**全ユーザー接続のペイロードが転送されてきます**。
ペイロードには Discord ユーザーID と視聴中トラック情報が含まれます。

#### (b) 任意のユーザーIDを占有し、正規ユーザーを追い出せる

`web_app.py:225-235`

```python
for u_id in ws_id:
    try:
        users_ws[u_id].write_message(json.dumps({"op": "disconnect",
                                       "reason": "別の場所で新しいセッションが開始されました..."}))
        users_ws[u_id].close(code=4200)
    except:
        pass
    users_ws[u_id] = self
```

任意の `user_ids`（最大3件）で接続すると、**そのユーザーの既存 RPC セッションを
切断して自分に差し替えられます**。`ENABLE_RPC_AUTH` のトークン検証
（`web_app.py:166-185`）は**ボット→ユーザー方向の配信時にしか働かず**、
このユーザー登録経路には一切かかりません。

#### (c) `check_origin` が常に `True`

`web_app.py:246-247`

```python
def check_origin(self, origin: str):
    return True
```

任意の Web ページから WebSocket を張れます（Cross-Site WebSocket Hijacking）。

#### (d) `/` が認証なしで内部情報を開示する

`web_app.py:76-77, 129`

```python
for identifier, exception in self.pool.failed_bots.items():
    failed_bots.append(f"<tr><td>{identifier}</td><td>{exception}</td></tr>")
...
msg += f"\nデフォルトプレフィックス: {self.pool.config['DEFAULT_PREFIX']}<br><br>"
```

`app.listen(port=...)`（`web_app.py:435`）は既定で `0.0.0.0` にバインドし、
既定ポートは 80 です。**認証なしのページで**、初期化に失敗したトークンの識別子と
例外文字列、デフォルトプレフィックスが公開されます。
`{exception}` は HTML エスケープされておらず（`self.write()` は生 HTML）、
例外文字列に外部由来の値が混ざれば XSS になります。

#### (e) その他

- `web_app.py:149` の `json.loads(message)` に `try` がなく、不正フレームで例外
- `users_ws[data["user"]].token != token`（`web_app.py:172`）は非定時間比較
  （`secrets.compare_digest` を推奨）

**評価と推奨対応**

既定では `RUN_RPC_SERVER=false`（`.example.env:244`）なので、**デフォルト構成では
露出しません**。README も「プライベート使用を想定」としています。
しかし `RUN_RPC_SERVER=true` にした利用者は、上記をすべて背負います。

1. **最優先**: `.example.env` の `RUN_RPC_SERVER` 付近に
   「有効化すると認証なしのエンドポイントが公開される。インターネットに直接
   公開せず、リバースプロキシで認証をかけること」と明記する（文書のみ、1分）。
2. `check_origin` を `config["RPC_ALLOWED_ORIGINS"]` によるホワイトリストにする。
3. `is_bot` 経路に共有シークレット（`.env` の `RPC_BOT_SECRET`）を要求する。
4. `ENABLE_RPC_AUTH` が真のとき、**ユーザー登録経路でもトークンを検証**する。
5. `IndexHandler` の `{exception}` / `{identifier}` を
   `tornado.escape.xhtml_escape()` に通し、失敗ボット一覧は
   ローカルアクセスまたは認証時のみ表示する。

---

### R-7 【中】Docker イメージに `.env` と `.git` が焼き込まれる

`.Dockerfile:20`

```dockerfile
COPY . .
```

`.dockerignore`（全4行）:

```
venv
.java
.idea
.logs
.vscode
```

**`.env`、`.git/`、`__pycache__/`、`local_database/`、`application.yml`、
`database.json`、`.player_sessions/` がいずれも除外されていません。**

**影響**: ローカルで一度ボットを動かした（= `.env` に Discord トークンや
MongoDB URL、Spotify シークレットが入っている）ディレクトリで `docker build` すると、
**Discord トークンを含むイメージができます**。そのイメージを push すれば
トークンが公開されます。`.git/` の同梱でイメージサイズも無駄に膨らみます。

**修正**: `.dockerignore` を `.gitignore` に揃える。

```
.git
.gitignore
.env
__pycache__/
*.py[cod]
venv
.venv
.java
.logs
.idea
.vscode
local_database/
.player_sessions/
.db_cache/
database.json
application.yml
application.yml.old
*.jar
```

**同ファイルの付随指摘**

- **ファイル名が `.Dockerfile`（先頭ドット）**なので、`docker build .` では認識されません。
  `-f .Dockerfile` が必須です。意図的に「使わせない」ためなら README に明記し、
  そうでなければ `Dockerfile` にリネームしてください。
- ビルド用の `gcc` / `git` が最終イメージに残ります（`.Dockerfile:22-25`）。
  マルチステージ化、または `pip install` 後に `apt-get purge` を推奨。
- `USER` 指定がなく **root で実行**されます。非 root ユーザーを追加してください。
- `COPY . .` が `RUN pip install -r requirements.txt` より前にあるため、
  ソースを1文字変えるだけで依存インストールが再実行されます。
  `requirements.txt` を先に COPY してレイヤキャッシュを効かせるのが定石です。
- `EXPOSE 8080` ですが `web_app.py:435` の既定ポートは 80 です。
  `PORT` 環境変数を設定しないと不整合になります。

---

### R-8 【低】Spotify アクセストークンが `/tmp` に他ユーザー読み取り可能で保存される

L-9 と同一の事象です。修正は `spotify.py:189` の直後に `os.chmod(..., 0o600)` を
追加するか、キャッシュ先をプロジェクト配下に移す（1〜2行）。

---

### R-9 【低】`kill 1` によるプロセス再起動がコンテナ前提

`modules/error_handler.py:141, 303` / `utils/client.py:269`

```python
await asyncio.create_subprocess_shell("kill 1")
```

**PID 1 がボット自身であること**（= コンテナ内で PID 1 として起動していること）を
前提にしています。README が案内する `source_start.sh` 経由の実行では
PID 1 は init / systemd です。root で動かしていれば init にシグナルを送ろうとします
（通常は失敗しますが、意図した再起動も起きません）。

**修正**: `os.getpid()` を対象にする、または `sys.exit()` +
プロセスマネージャ（systemd / supervisor）による再起動に任せる。
シェル経由ではなく `os.kill(os.getpid(), signal.SIGTERM)` が明快です。

---

## 構造的負債

### R-10 【高】巨大関数・巨大クラス

| 箇所 | 種類 | 行数 |
|---|---|---|
| `modules/music.py:606` `play` | 関数 | **1,458** |
| `modules/music.py:5282` `player_controller` | 関数 | 694 |
| `modules/music_settings.py:378` `setup` | 関数 | 535 |
| `utils/client.py:569` `setup` | 関数 | 434 |
| `utils/music/models.py:2496` `invoke_np` | 関数 | 375 |
| `utils/music/models.py:1466` `get_autoqueue_tracks` | 関数 | 334 |
| `utils/music/models.py:1838` `_process_next` | 関数 | 331 |
| `modules/player_resume.py:367` `resume_player` | 関数 | 325 |
| `modules/music.py:51` `Music` | **クラス** | **7,723** |
| `utils/music/models.py:500` `LavalinkPlayer` | クラス | 3,323 |

`play`（1,458行）が単体で `utils/db.py` 全体（327行）の4倍以上あります。

**分割方針の提案**（`play` を例に）

1. **入力の正規化** → `utils/music/query_resolver.py`
   URL 判定・プロバイダ判定・プレイリスト展開（Spotify / Deezer / YouTube の分岐）
2. **事前チェック** → 既存の `utils/music/checks.py` へ寄せる
   権限・VC 状態・チャンネル上限・クールダウン
3. **プレイヤー確保** → `LavalinkPlayer.get_or_create(...)`
4. **キュー投入と応答生成** → `utils/music/enqueue.py`

`Music` クラス（7,723行）は**コマンドのグルーピングで最低4分割**できます:

| 新モジュール | 移す内容 |
|---|---|
| `modules/music_playback.py` | `play`, `skip`, `pause`, `seek`, `stop` |
| `modules/music_queue.py` | `clear`(:3904), `do_move`(:4249), `rotate`, `shuffle`, `remove` |
| `modules/music_controller.py` | `player_controller`(:5282), スキン連携 |
| `modules/music_songrequest.py` | `song_requests`(:6110) |

全体書き換えは非現実的なので、**新規機能追加のたびに該当部分だけを切り出す**
「触ったところから直す」漸進的アプローチを推奨します。

---

### R-11 【高】裸の `except:` が365箇所、うち190箇所が無言で握り潰している

```
$ grep -rn "except:" --include="*.py" . | wc -l
365
$ 直後が pass または continue
190
```

| ファイル | 件数 |
|---|---|
| `modules/music.py` | **102** |
| `utils/music/models.py` | **91** |
| `modules/music_settings.py` | 27 |
| `modules/player_resume.py` | 19 |
| `utils/music/interactions.py` | 17 |
| `utils/others.py`, `utils/client.py`, `modules/misc.py`, `modules/error_handler.py` | 各10 |

**問題点**

- 裸の `except:` は `KeyboardInterrupt` / `SystemExit` も捕まえます
  （`asyncio.CancelledError` は Python 3.8 以降 `BaseException` 直下なので免れます）。
- 190箇所が `pass` / `continue` なので、**バグが完全に不可視**になります。
  R-1 の Spotify ハングのような不具合が本番で「なぜか無応答」として現れる温床です。

**段階的な改善方針**

1. まず `except:` → `except Exception:` に機械置換する（`BaseException` の誤捕獲を排除）。
   挙動変化のリスクが極小で、効果は全体に及びます。
2. `pass` で潰している箇所に、意図が分かる形でログを入れる。
   ```python
   except Exception:
       logging.debug("メッセージ削除に失敗（既に削除済みの可能性）", exc_info=True)
   ```
3. 想定される例外が分かる箇所から順に `except (disnake.NotFound, disnake.Forbidden):` へ狭める。
   Discord API 起因の `NotFound` / `Forbidden` を潰す意図の箇所が大半と見られます。

---

### R-12 【中】BOM（U+FEFF）が11ファイルに混在

```
utils/music/interactions.py
utils/music/skins/normal_player/classic.py
utils/music/skins/normal_player/default.py
utils/music/skins/normal_player/default_progressbar.py
utils/music/skins/normal_player/embed_link.py
utils/music/skins/normal_player/lite.py
utils/music/skins/normal_player/micro_controller.py
utils/music/skins/normal_player/micro_nc.py
utils/music/skins/normal_player/mini.py
utils/music/skins/normal_player/minimalist.py
utils/music/skins/normal_player/miniplayer.py
```

`normal_player/` の**スキン10ファイル全部**と `interactions.py` に BOM があり、
`static_player/` 側には1つもありません。日本語化作業時に Windows のエディタが
付与したものと推測されます。

**影響**: Python のトークナイザは UTF-8 BOM を許容するため**実行は正常**です
（`py_compile` 全59ファイル成功で確認）。しかし:

- `ast.parse(open(f).read())` は `SyntaxError: invalid non-printable character U+FEFF` で失敗します。
  実際にこのレビューでのメトリクス収集が最初に失敗しました。
- `encoding='utf-8-sig'` を使わない解析系ツール（自作スクリプト、一部の静的解析、
  一部の diff ツール）が壊れます。
- `git diff` の1行目が常にノイズになります。

**修正**（安全・1コマンド）:

```bash
for f in utils/music/interactions.py utils/music/skins/normal_player/*.py; do
  sed -i '1s/^\xEF\xBB\xBF//' "$f"
done
```

**再発防止**: `.gitattributes` は既に存在するので、そこに `*.py text eol=lf` を追記し、
`.editorconfig` で `charset = utf-8` を指定してください。

---

### R-13 【中】`aiohttp.ClientSession` を17箇所で使い捨てている

```
$ grep -rn "ClientSession()" --include="*.py" . | wc -l
17
```

| 箇所 | 備考 |
|---|---|
| `utils/music/audio_sources/deezer.py:29` | **API リクエストごとに新規生成** |
| `utils/music/audio_sources/spotify.py:68, 160` | 同 |
| `utils/music/lastfm_tools.py:47` | 同 |
| `utils/uptime_kuma.py:18` | **60秒ごとに新規生成** |
| `modules/lastfm.py:647`, `modules/misc.py:999`, `modules/music.py:1939, 7769`, `modules/legacy_cmds.py:1133`, `modules/ll_yt_oauth.py:112`, `modules/error_handler.py:523`, `utils/client.py:350, 385` | 単発なので影響小 |

`async with` で閉じられているのでリークはありませんが、**コネクションプールと DNS
キャッシュが毎回破棄**されます。プレイリスト展開のように短時間に何十回も叩く経路
（`deezer.py:29` の `request()`）では、TCP + TLS ハンドシェイクが毎回発生して
明確に遅くなります。

**修正**: `utils/client.py:878` に既に `bot.session = aiohttp.ClientSession()` があるので、
`DeezerClient` / `SpotifyClient` / `LastFmApi` のコンストラクタに session を注入し、
そちらを使い回してください。`ll_yt_oauth.py:180` などは既に `self.bot.session` を
使っており、**同一プロジェクト内で流儀が分かれている**のが実態です。

`utils/uptime_kuma.py` は独立性が高いので、ループ外で1つ作る形が素直です:

```python
async def kuma_heartbeat():
    push_url = os.getenv("UPTIME_KUMA_PUSH_URL")
    if not push_url:
        print("[KUMA] UPTIME_KUMA_PUSH_URL が未設定のためハートビートを無効化")
        return

    print("[KUMA] ハートビート開始")
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        while True:
            try:
                async with session.get(push_url):
                    pass
            except Exception as e:
                print(f"[KUMA] heartbeat failed: {type(e).__name__}")
            await asyncio.sleep(60)
```

**`utils/uptime_kuma.py` の付随指摘**

- `os.getenv("UPTIME_KUMA_PUSH_URL")` を直接読んでおり、プロジェクト全体の
  設定機構（`config_loader.load_config()` → `bot.config[...]`）を迂回しています。
  そのため **`config.json` や `.env` 以外の設定手段では効きません**。
  他の設定項目と同様に `config_loader.py` の `DEFAULT_CONFIG` に登録し、
  `bot.config["UPTIME_KUMA_PUSH_URL"]` から読むべきです。
- `print()` 直書きです。プロジェクトは `logging` も併用しているので、
  `logging.getLogger(__name__)` に寄せると運用時に制御できます。
- `utils/client.py:944-945` は `self.loop.create_task(...)` の戻り値を保持していません。
  参照が残らないと GC で回収され得ます（実際は無限ループなので稀ですが）。
  タスク参照を `self` に保持し、シャットダウン時にキャンセルしてください。

---

### R-14 【中】トークンのマスク処理が5箇所にコピーされ、1箇所が抜けている

L-10 と同一の事象です。コード品質の観点から再掲します。

```python
repr(error)[:2030].replace(self.bot.http.token, 'mytoken')
```

この式が `modules/error_handler.py:117, 255, 263` / `modules/music.py:6349` /
`utils/owner_panel.py:75` の**5箇所に重複**しており、
`error_handler.py:150-153` と `:312-315`（Webhook 添付の完全トレースバック）**だけが
適用漏れ**です。これはコピペ由来の典型的な抜けです。

**修正**: `utils/others.py` に1箇所へ集約する。

```python
def redact_secrets(text: str, bot) -> str:
    """ログ・レポートに出す文字列から秘密情報を除去する。"""
    for secret in filter(None, (bot.http.token, bot.config.get("MONGO"))):
        text = text.replace(secret, "[REDACTED]")
    return text
```

`repr(error)` を出す全経路と `string_to_file(full_error_msg, ...)` の両方から
必ずこれを通すようにしてください。MongoDB URL も同時に潰せるので一石二鳥です。

---

### R-15 【中】ベンダリングした `wavelink/` がアプリケーションコードに依存している（依存方向の逆転）

`wavelink/node.py:36`

```python
from utils.music.youtube_trusted_session_generator import Browser
```

`wavelink/` は本来独立した third-party パッケージです。それがアプリケーション側の
`utils/` をトップレベルで import しているため:

- `wavelink/` を単体で取り出せず、上流 wavelink への追従が事実上不可能になっています。
- **L-1 の AGPL 混入が「中核モジュールの起動時ロード」になっている原因**が、まさにこれです。
- `utils/` → `wavelink/` の依存も存在するため、循環依存の構造になっています。

**修正**: `Node` に poToken 取得を**コールバックとして注入**し、
`wavelink/` から `utils/` への import を撤去してください。

```python
# wavelink/node.py
class Node:
    def __init__(self, ..., potoken_provider: Optional[Callable[[], Awaitable[dict]]] = None):
        self._potoken_provider = potoken_provider
```

呼び出し側（`utils/music/models.py` などの Node 生成箇所）で
`potoken_provider=generate_potoken` を渡します。
これは **L-1 の分離案 (a) と同じ作業**なので、リーガル対応と同時に片付きます。

---

### R-16 【中】ユーザーに見えるポルトガル語が残っている

README は「完全日本語化」を謳い、`.example.env` は実際に翻訳完了していますが、
**起動時・ダウンロード時に必ず表示される文字列が未翻訳**です。

| 箇所 | 文字列 | 露出タイミング |
|---|---|---|
| `utils/music/local_lavalink.py:139` | `Download do arquivo {filename} {current_progress}% concluído (...)` | **Lavalink.jar ダウンロード中（初回起動時に必ず）** |
| `utils/music/local_lavalink.py:141` | `Download do arquivo {filename} {current_progress}% concluído` | 同 |
| `utils/music/local_lavalink.py:595` | `🌋 - Iniciando o servidor Lavalink (dependendo da hospedagem ...` | **ローカル Lavalink 起動時に毎回** |
| `utils/music/local_lavalink.py:491` | `JDK não encontrando no diretório: ...` | JDK 検出失敗時 |
| `utils/music/local_lavalink.py:185-186` | `Falha ao obter versão do java...` | Java 検証失敗時 |
| `wavelink/node.py:208` | `📶 - {bot} - Iniciando servidor de música: {identifier}` | **ノード接続時に毎回** |
| `wavelink/node.py:226, 231` | `❌ - Falha ao conectar no servidor [...]` | ノード接続失敗時 |
| `wavelink/player.py:532, 555, 666` | `Ocorreu um erro ao destruir player: ...` 等 | 例外メッセージ |
| `utils/music/audio_sources/spotify.py:167` | `⚠️ - Spotify: Ocorreu um erro ao obter token: ...` | **R-1 のハング直前に出る唯一の手がかり** |
| `config_loader.py:49, 82, 89, 99, 120` | `### Sistema de música ###` 等 | コメント（内部のみ） |
| `utils/music/remote_lavalink_serverlist.py:1` | `# pip install requests ou adicione ...` | コメント |

**特に `local_lavalink.py:139/141/595` はフォークが積極的に保守しているファイル**であり、
初回セットアップで日本語ユーザーが最初に目にする出力です。優先的に翻訳してください。

`spotify.py:167` は R-1 の無限ハング時に出る唯一のログなので、
バグ修正とあわせて日本語化する価値が高いです。

---

### R-17 【中】スキン実装に大量の重複がある

`utils/music/skins/` は15ファイル・計2,808行で、全ファイルが同一シグネチャの
`load()` を持ちます。

| ファイル | 行数 |
|---|---|
| `static_player/default_progressbar.py` | 325 |
| `static_player/default.py` | 315 |
| `static_player/mini.py` | 290 |
| `normal_player/default_progressbar.py` | 267 |
| `normal_player/default.py` | 259 |
| `normal_player/classic.py` | 229 |
| `static_player/embed_link.py` | 218 |
| `static_player/classic.py` | 216 |
| `normal_player/mini.py` | 215 |
| `normal_player/embed_link.py` | 175 |
| （以下 39〜78行の小型スキン5件） | |

`static_player/default_progressbar.py:28 load` は289行、
`static_player/default.py:27 load` は279行で、**内容の大半が共通**です
（Embed 構築、トラック情報整形、ボタン配置、キュー表示）。

**修正方針**: `utils/music/skin_utils.py`（既存・237行）を土台に、
共通部分をヘルパへ抽出してください。

- `build_track_embed(player, *, show_progressbar: bool, show_queue: int) -> disnake.Embed`
- `build_controller_buttons(player, *, style: str) -> list[disnake.ui.Item]`
- `format_queue_preview(player, limit: int) -> str`

各スキンは「どのパーツをどう組むか」の宣言だけにできるはずです。
README がユーザーによるカスタムスキン作成を推奨している以上、
**スキン API を薄くすることは機能価値にも直結**します。

---

### R-18 【中】テスト・CI・リンタが一切ない

| 項目 | 状態 |
|---|---|
| テストファイル | **0**（`git ls-files \| grep -iE "test\|spec"` → 空） |
| `.github/` | **存在しない** |
| `pyproject.toml` / `setup.cfg` / `.ruff.toml` / `.flake8` | **存在しない** |
| `.pre-commit-config.yaml` | 存在しない |
| `.editorconfig` | 存在しない |

**このレビューで見つかった R-1〜R-5 のほとんどは、最小限の仕組みで自動検出できたものです。**

**費用対効果の高い順に導入を推奨します。**

**1. GitHub Actions で構文チェック（最小・即効）**

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  syntax:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - name: 構文チェック
        run: python -m compileall -q .
      - name: BOM 検出
        run: |
          if grep -rlP '^\xEF\xBB\xBF' --include='*.py' .; then
            echo "::error::BOM 付きファイルがあります"; exit 1
          fi
```

**2. ruff（設定ゼロで始められる）**

```toml
# pyproject.toml
[tool.ruff]
target-version = "py310"
line-length = 120
exclude = ["wavelink"]   # ベンダリング分は当初除外

[tool.ruff.lint]
select = ["E9", "F63", "F7", "F82", "E722"]
# E9/F63/F7/F82 = 構文エラー・未定義名などの致命的問題
# E722 = 裸の except（R-11 の再発防止）
```

`select` をこの5つに絞れば既存コードでもほぼ通り、**新規の裸 except だけを止められます**。
慣れてから `F401`（未使用 import）などを足していく運用が現実的です。

**3. 設定値の整合テスト（R-4 / L-4 の再発防止）**

`.example.env` と `config_loader.DEFAULT_CONFIG` のキーと重要な値が
乖離していないか検証する 20行程度のテストを追加してください。
L-4 の `SOURCE_REPO` 不整合はこれで確実に捕まります。

**4. `utils/music/local_lavalink.py` の単体テスト**

`is_snapshot_version()`（:188）、`update_youtube_plugin()`（:235）、
`restore_youtube_credentials()`（:193）は**外部依存のない純粋なロジック**で、
フォークの中核価値そのものです。ここだけでもテストを書く価値が最も高い箇所です。

---

### R-19 【低】オーナーパネルが各コマンドの `checks` をバイパスしている

`utils/owner_panel.py:53-54`

```python
async def opts_callback(self, interaction: disnake.MessageInteraction):
    txt = await self.bot.get_command(interaction.data.values[0])(interaction)
```

`Command.__call__` はコールバックを直接呼ぶため、各コマンドに付いている
`@commands.is_owner()` が**実行されません**。

**これは脆弱性ではありません。** `PanelView.interaction_check`（`utils/owner_panel.py:64-70`）が
`await self.bot.is_owner(interaction.user)` で正しくガードしており、
非オーナーは弾かれます。この点は問題なしと確認しました。

ただし、**認可が `interaction_check` 単一箇所に依存**しているのは
多層防御の観点で脆い設計です。`interaction_check` にリグレッションが入った瞬間、
`update` / `exportsource` / `shell` 相当の操作が誰でも実行できる状態になります。

**推奨**: `interaction_check` を維持したうえで、`opts_callback` を
`ctx.invoke()` 相当（checks を通る呼び出し）に変更し、二重に防御してください。

**同ファイルの軽微な指摘**

- `interaction_check` が失敗時に `return`（= `None`）を返しています。
  偽値なので動作しますが、明示的に `return False` が正しいです。
- `custom_id="onwer_panel_dropdown"`（`utils/owner_panel.py:46`）は
  `owner` のタイプミスです。永続 View の `custom_id` なので、
  変更すると**既に送信済みのパネルメッセージが動作しなくなります**。
  直すなら「次のメジャー更新時に、既存パネルの再送が必要」と周知した上で行ってください。

---

### R-20 【低】ベンダリングした wavelink 0.9.15 が上流 EOL 版である

`wavelink/__init__.py:5`

```python
__version__ = '0.9.15'
```

`__copyright__ = 'Copyright 2019-2021 (c) PythonistaGuild'` から、2021年時点の版です。
上流 wavelink はその後メジャーバージョンを重ねており、0.9.x はサポート外です。
本プロジェクトは Lavalink v4 対応のため独自に改変しているため（`player.py:555` に
`"Não implementado para lavalink v4 (ainda)"` = 「Lavalink v4 では未実装（まだ）」という
未完了マーカーが残っています）、**実質的に上流から分岐した独自フォーク**です。

**推奨**: 上流追従は現実的でないため、以下を明示してください。

- `wavelink/README.md` を追加し、「PythonistaGuild/Wavelink 0.9.15 を Lavalink v4 対応の
  ため改変したフォーク。上流への追従は行わない」と記載（L-12 の改変告知と同時に片付きます）。
- `player.py:555` の未実装箇所が到達可能かを確認し、到達するなら実装するか、
  到達しないなら削除してください。

---

### R-21 【低】非同期関数内の同期 I/O

`ast` 解析で検出した、`async def` 内の同期 `open()` は10箇所です。

| 箇所 | 関数 |
|---|---|
| `modules/ll_yt_oauth.py:246, 259` | `oauth_command` |
| `modules/legacy_cmds.py:330, 443, 734, 1136` | `update`, `update_deps`, `exportsource`, `download_lavalink_serverlist` |
| `utils/client.py:1117, 1135, 1138` | `sync_app_commands` |
| `utils/db.py:258` | `update_from_json` |

いずれもオーナー専用コマンドか起動時処理で、頻度が低く小さいファイルなので
**実害はほぼありません**。ただし `aiofiles` は既に依存に入っており
（`modules/misc.py:882` などで使用中）、プロジェクト内で流儀が分かれています。
新規コードは `aiofiles` に寄せるのが一貫します。

なお `utils/music/local_lavalink.py` の同期処理（`requests`、`subprocess`）は
`utils/client.py:224` で `run_in_executor` 経由で呼ばれており、**適切です**。

---

## 第2部まとめ

| ID | 深刻度 | 概要 | 修正の重さ |
|---|---|---|---|
| R-1 | **高** | Spotify 認証エラー時に永久ハング（`token_refresh` が解放されない） | **小（try/finally）** |
| R-6 | **高** | RPC WS に認証がなく、`bot:true` 自称で全ユーザーの再生情報を取得可能 | 中（既定は無効） |
| R-10 | **高** | 巨大関数・巨大クラス（`play` 1,458行 / `Music` 7,723行） | 大（漸進的に） |
| R-11 | **高** | 裸の `except:` 365箇所、うち190箇所が無言で握り潰し | 中（機械置換から） |
| R-7 | 中 | Docker イメージに `.env` / `.git` が焼き込まれる | **小（`.dockerignore`）** |
| R-2 | 中 | `web_app.py:280` `on_close()` の `ValueError` | **1行** |
| R-3 | 中 | `ll_yt_oauth.py:259` の `encoding` 漏れで Windows で yml 破損 | **1行** |
| R-12 | 中 | BOM が11ファイルに混在（`ast` 解析が失敗） | **1コマンド** |
| R-13 | 中 | `ClientSession` を17箇所で使い捨て | 小 |
| R-14 | 中 | トークンマスクが5箇所に重複し1箇所が抜け | 小 |
| R-15 | 中 | `wavelink/` がアプリコードに依存（依存方向の逆転・L-1 の原因） | 中 |
| R-16 | 中 | ユーザー可視のポルトガル語が残存（起動時に必ず表示） | 小 |
| R-17 | 中 | スキン15ファイル2,808行に大量の重複 | 中 |
| R-18 | 中 | テスト・CI・リンタが皆無 | 小（段階導入） |
| R-4 | 低 | `updatelog` にオーナー制限が抜け | **1行** |
| R-5 | 低 | `remote_git_url` のパースが壊れやすい | 小 |
| R-8 | 低 | Spotify トークンが `/tmp` に他ユーザー読み取り可能で保存 | **1行** |
| R-9 | 低 | `kill 1` がコンテナ前提 | 小 |
| R-19 | 低 | オーナーパネルが checks をバイパス（`interaction_check` 単独依存） | 小 |
| R-20 | 低 | wavelink 0.9.15（上流 EOL）のベンダリング | 文書のみ |
| R-21 | 低 | `async def` 内の同期 `open()` 10箇所 | 小 |

---

# 推奨アクションプラン

修正コストと効果で並べました。

## フェーズ1: 1行〜1コマンドで終わるもの（所要 1時間以内）

| # | 対応 | 該当 |
|---|---|---|
| 1 | `requirements.txt:27` の `undetected-chromedriver` を削除（**未使用**） | L-1 |
| 2 | `.example.env:131` の `SOURCE_REPO` をフォーク URL に修正 | L-4 |
| 3 | `modules/ll_yt_oauth.py:259` に `encoding='utf-8'` を追加 | R-3 |
| 4 | `web_app.py:280` を `if self in bots_ws:` でガード | R-2 |
| 5 | `.dockerignore` に `.env` / `.git` 等を追加 | R-7 |
| 6 | BOM を11ファイルから除去 | R-12 |
| 7 | `modules/legacy_cmds.py:540` に `@commands.is_owner()` を追加 | R-4 |
| 8 | `spotify.py:189` の後に `os.chmod(..., 0o600)` | L-9 / R-8 |
| 9 | README: 「一部翻訳中」削除、`@claude`/Anthropic クレジット修正 | L-11 |

## フェーズ2: 数時間規模（バグ修正と法務の手続要件）

| # | 対応 | 該当 |
|---|---|---|
| 10 | `spotify.get_access_token()` を `try/finally` 化し再帰を除去 | **R-1** |
| 11 | README の本家に関する記述を修正（アーカイブ解除済み・最終更新は 2026-03-02・HEAD は取り込み済み・差分確認コマンドの追記） | L-11(a) |
| 12 | `redact_secrets()` に集約し Webhook 経路にも適用 | L-10 / R-14 |
| 13 | `LICENSE` / `NOTICE` に著作権表示を追加、`CHANGES.md` で変更告知 | L-2 / L-3 |
| 14 | `PRIVACY.md` を作成（収集項目・第三者提供・削除手順） | L-8 |
| 15 | `local_lavalink.py:139/141/595` 等のポルトガル語を日本語化 | R-16 |
| 16 | `.example.env` の `RUN_RPC_SERVER` にセキュリティ注意書きを追加 | R-6 |
| 17 | GitHub Actions（`compileall` + BOM 検出）と ruff 最小設定を追加 | R-18 |
| 18 | `wavelink/meta.py` に MIT ヘッダ、`wavelink/README.md` に改変告知 | L-12 / R-20 |

## フェーズ3: 設計変更（L-1 の解消を含む）

| # | 対応 | 該当 |
|---|---|---|
| 19 | `youtube_trusted_session_generator` を別リポジトリ（AGPL-3.0）へ分離し、`wavelink/node.py:36` のトップレベル import を撤去。poToken は既存 `ytpotoken` 経路で受け取る | **L-1 / R-15** |
| 20 | RPC WebSocket に認証を追加（`bot:true` の検証、origin ホワイトリスト、ユーザー登録経路のトークン検証、HTML エスケープ） | R-6 |
| 21 | `except:` → `except Exception:` へ機械置換し、`pass` 箇所にログを追加 | R-11 |
| 22 | `ClientSession` を `bot.session` に統合 | R-13 |
| 23 | `local_lavalink.py` の純粋関数に単体テストを追加 | R-18 |

## フェーズ4: 長期（漸進的に）

| # | 対応 | 該当 |
|---|---|---|
| 24 | `Music` クラスを4モジュールに分割、`play` を4層に分解 | R-10 |
| 25 | スキン共通処理を `skin_utils.py` に抽出 | R-17 |

---

## 所見

**フォーク独自の作業品質は高い**と評価します。`local_lavalink.py` の
youtube-source 自動更新、SHA-256 検証、jabba スクリプトのコミット固定、
不完全ダウンロードの検出、`.tmp` への書き込みと `os.rename` による原子的置換など、
いずれも「なぜそうするか」をコメントで残した上で堅牢に実装されています。
`modules/misc.py:653` の GPL-2 §3 への言及は、ライセンスへの意識の高さを示しています。

**最も重要な2点は、いずれもその意識と現状の間のギャップです。**

1. **L-1**: GPL-2.0-only を維持しながら AGPL-3.0 ライブラリを中核経路で import しており、
   再配布時にライセンス違反になります。`undetected-chromedriver` の削除は今日できます。
   `nodriver` の分離は設計変更ですが、`ytpotoken` による手動経路が既にあるため、
   道筋は見えています。
2. **L-4**: `/about` のソースリンクを直した意図が、`.example.env` の1行で無効化されています。
   **1行の修正で、コード側の配慮が実際に機能するようになります。**

`py_compile` が全ファイル通ること、`.example.env` の翻訳が完了していること、
フォークが触った箇所のコメント品質が高いことは、いずれも実測で確認しました。
残る指摘の大半は本家由来の構造的負債であり、一度に解消する必要はありません。
フェーズ1の9項目だけでも、実害のある不具合と法務リスクの相当部分が片付きます。
