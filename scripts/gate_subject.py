"""해부학 과목의 index.html에 로그인 문을 단다.

    uv run --python 3.13 python scripts/gate_subject.py <Pages 저장소> [과목 …]

해부학 넷은 각자 완성된 한 파일짜리 앱이라 다시 쓰지 않는다. **문이 되는
자리만 갈아 끼운다** — 네 곳이고, 네 과목이 거의 같은 코드라 한 번에 된다.

    ① 문항 DB를 `<script src="quiz_db.js">`로 읽던 것을 로그인 뒤 API에서 받는다
    ② 사진 경로를 만들던 함수가 서명 URL을 돌려주게 한다
    ③ 한 판(30문항)을 시작할 때 그 30장을 미리 서명받는다
    ④ 공용 스크립트 넷(config·session·auth·gate)을 머리에 단다

**여러 번 돌려도 같다.** 이미 개조된 파일은 건너뛴다.

원본을 고치는 것이 아니라 배포 저장소의 사본을 고치는 것이므로, 과목 앱을
누가 새로 구우면 여기를 다시 돌려야 한다. 그 사실을 파일 첫머리에 적어 둔다.
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

MARK = "<!-- gated: scripts/gate_subject.py -->"

HEAD = MARK + """
<!-- 이 파일은 로그인 문이 달려 있다. 과목 앱을 새로 구우면 이 표시가 사라지고,
     그때는 scripts/gate_subject.py 를 다시 돌려야 한다. 안 돌리면 그 과목만
     로그인 없이 열린다. -->
<script src="../config.js"></script>
<script src="../session.js"></script>
<script src="../auth.js"></script>
<script src="../gate.js"></script>"""

# ① 문항 DB를 담을 자리. quiz_db.js 가 `const QUIZ_DB` 로 주던 것을 대신한다.
DECL = """        let QUIZ_DB = [];

"""

# ② 사진 이름 → 서명 URL. 원래는 폴더 경로와 확장자 후보를 만들던 함수다.
#    후보를 하나로 줄여도 되는 것은 문항이 가리키는 사진이 전부 실재함을
#    올리기 전에 확인했기 때문이다(scripts/upload_subject.py).
CANDIDATES = """        function imageNameOf(itemOrFilename) {
            const raw = (typeof itemOrFilename === "object" && itemOrFilename !== null)
                ? (itemOrFilename.image_path || itemOrFilename.image_filename || "")
                : (itemOrFilename || "");
            return String(raw).replace(/\\\\/g, "/").split("/").pop();
        }

        function buildImageCandidates(itemOrFilename) {
            const name = imageNameOf(itemOrFilename);
            const url = name ? GATE.image(name) : "";
            return url ? [url] : [];
        }
"""


def patch_common(text, subject):
    """exam1 · trunk · head-neck. 셋이 같은 코드에서 나왔다."""
    # onload 의 **여는 줄만** 맞춘다. 과목마다 그 안에 든 줄이 달라서
    # (exam1 은 마커를 다시 그리는 리스너가 하나 더 있다) 블록 전체로 맞추면
    # 한 과목만 통과하고 나머지가 조용히 안 걸린다.
    old_onload = "        window.onload = function() {"
    new_onload = """        window.onload = function() {
            // 로그인 뒤에야 문항이 온다. 그 전에는 GATE 가 화면을 덮고 있다.
            GATE.start('%s', async (db) => { QUIZ_DB = db; });""" % subject
    if old_onload not in text:
        raise SystemExit(f"[{subject}] window.onload 를 못 찾았다")
    text = text.replace(old_onload, DECL + new_onload, 1)

    # 옛 후보 생성기를 통째로 갈아 끼운다.
    start = text.index("        function buildImageCandidates(itemOrFilename) {")
    end = text.index("        function setQuestionImage(", start)
    text = text[:start] + CANDIDATES + "\n" + text[end:]

    # 한 판을 시작할 때 그 30장을 미리 서명받는다.
    old_start = "        function startQuiz(mode) {"
    text = text.replace(old_start, "        async function startQuiz(mode) {", 1)
    old_load = """            document.getElementById('quiz-container').style.display = 'flex';
            loadQuestion(0);"""
    new_load = """            document.getElementById('quiz-container').style.display = 'flex';
            // 사진은 서명 URL이라 미리 받아 둬야 한다. 한 판이 30문항이라
            // 한 번에 받는다 — 문항마다 부르면 왕복이 30번이 된다.
            await GATE.prefetch(quizData.map(imageNameOf));
            loadQuestion(0);"""
    if old_load not in text:
        raise SystemExit(f"[{subject}] startQuiz 의 loadQuestion(0) 을 못 찾았다")
    return text.replace(old_load, new_load, 1)


def patch_neuro(text, subject):
    """neuro 는 후보 생성기 없이 `image_filename` 을 그대로 src 에 넣는다."""
    old_onload = "    window.onload = function() {"
    new_onload = """    let QUIZ_DB = [];

    function imageNameOf(item) {
      const raw = (item && (item.image_path || item.image_filename)) || "";
      return String(raw).replace(/\\\\/g, "/").split("/").pop();
    }
    function imageUrlOf(item) {
      const name = imageNameOf(item);
      return name ? GATE.image(name) : "";
    }

    window.onload = function() {
      // 로그인 뒤에야 문항이 온다. 그 전에는 GATE 가 화면을 덮고 있다.
      GATE.start('%s', async (db) => { QUIZ_DB = db; });""" % subject
    if old_onload not in text:
        raise SystemExit(f"[{subject}] window.onload 를 못 찾았다")
    text = text.replace(old_onload, new_onload, 1)

    swaps = [
        ("      imgEl.src = data.image_filename;", "      imgEl.src = imageUrlOf(data);"),
        ('      const url = data?.image_filename || "";', '      const url = imageUrlOf(data);'),
        ("      modalImg.src = data.image_filename;", "      modalImg.src = imageUrlOf(data);"),
    ]
    for old, new in swaps:
        if old not in text:
            raise SystemExit(f"[{subject}] 못 찾았다: {old.strip()}")
        text = text.replace(old, new, 1)

    text = text.replace("    function startQuiz(mode) {", "    async function startQuiz(mode) {", 1)
    old_load = "      loadQuestion(0);"
    new_load = """      await GATE.prefetch(quizData.map(imageNameOf));
      loadQuestion(0);"""
    if old_load not in text:
        raise SystemExit(f"[{subject}] loadQuestion(0) 을 못 찾았다")
    return text.replace(old_load, new_load, 1)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        raise SystemExit("Pages 저장소 경로를 주세요.")
    repo = os.path.abspath(args[0])
    subjects = args[1:] or ["exam1", "trunk", "head-neck", "neuro"]

    for subject in subjects:
        path = os.path.join(repo, subject, "index.html")
        if not os.path.isfile(path):
            raise SystemExit(f"없는 파일: {path}")
        text = open(path, encoding="utf-8").read()
        if MARK in text:
            print(f"  이미 됨  {subject}")
            continue

        tag = '<script src="quiz_db.js"></script>'
        if tag not in text:
            raise SystemExit(f"[{subject}] quiz_db.js 태그를 못 찾았다")
        text = text.replace(tag, HEAD, 1)
        text = (patch_neuro if subject == "neuro" else patch_common)(text, subject)

        open(path, "w", encoding="utf-8", newline="").write(text)
        print(f"  문 달았음 {subject}")


if __name__ == "__main__":
    main()
