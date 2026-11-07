#!/bin/sh
# 훅을 이 클론에 설치한다. 클론마다 한 번. 훅을 고친 뒤에도 다시 돌린다.
#
# .git/hooks(공용 디렉터리)로 복사한다. core.hooksPath=.githooks 로 걸면
# 경로가 작업본 안에서 풀려서, .githooks 가 없는 옛 커밋에 올라간 worktree는
# 아무 경고 없이 보호가 빠진다(2026-11-08 실측 확인). 복사본은 체크아웃된
# 브랜치와 무관하게 모든 worktree에서 돈다.
set -e

src_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
hooks_dir=$(git rev-parse --git-common-dir)/hooks
mkdir -p "$hooks_dir"

for h in pre-push; do
	cp "$src_dir/$h" "$hooks_dir/$h"
	chmod +x "$hooks_dir/$h"
	echo "installed: $hooks_dir/$h"
done

if [ -n "$(git config --get core.hooksPath 2>/dev/null)" ]; then
	git config --unset core.hooksPath
	echo "unset core.hooksPath (복사본을 쓴다)"
fi
