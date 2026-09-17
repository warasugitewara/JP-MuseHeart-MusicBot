# ベースイメージはDebian 12 (bookworm) を明示的に指定する。
# `python:3.10-slim` のままだと、タグが指すDebianのバージョンが変わった際に
# 下でコピーするJREとglibcのバージョンが噛み合わなくなる可能性がある。
FROM python:3.10-slim-bookworm

# Lavalinkの起動にはJava 17以上が必要（utils/music/local_lavalink.py の
# validate_java が17未満を弾く）。
# 以前は openjdk:11-jdk-slim からコピーしていたが、Java 11では要件を満たさず、
# かつ openjdk イメージ自体が非推奨化されタグも削除されているためビルドできない。
# Ubuntu 22.04ベース (glibc 2.35) のJREをbookworm (glibc 2.36) 上で使う。
COPY --from=eclipse-temurin:17-jre-jammy /opt/java/openjdk /opt/java/openjdk

ENV JAVA_HOME=/opt/java/openjdk

RUN update-alternatives --install /usr/bin/java java /opt/java/openjdk/bin/java 1

WORKDIR /usr/src/app

COPY . .

RUN apt-get update \
&& apt-get install -y --no-install-recommends gcc git \
&& apt-get clean \
&& rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "/usr/src/app/main.py"]

EXPOSE 8080
