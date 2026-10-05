/**
 * 이용방법. **고정 문서다** — 공지처럼 표에 두지 않았다. 화면이 바뀌면 이 글도
 * 같이 바뀌어야 하는데, 그 둘은 같은 커밋에서 바뀌는 편이 어긋나지 않는다.
 *
 * 2026-10-04 운영을 시작하며 섰다(`NoticesPage` 머리). 여기 적힌 버튼 이름과
 * 단축키는 그날의 화면에서 옮겨 왔다 — 화면의 문구를 고치면 이 글도 찾아 고친다.
 *
 *     칸의 두 자리 ·  ○ □      calendar/EventChip.tsx · CalendarPage.tsx 범례
 *     패널의 세 덩이            calendar/EventPanel.tsx · PreviewAction.tsx
 *     풀이 단축키               lecture/Quiz.tsx (`onKey`)
 *     모아받기                  bundle/BundleButton.tsx
 *     공부 흐름 그림의 색        styles/base.css `--fam-*` — 패널의 갈래 색 그대로
 */
const SECTIONS = [
  ["flow", "한눈에"],
  ["calendar", "캘린더 읽기"],
  ["panel", "강의 칸을 눌렀을 때"],
  ["quiz", "웹에서 풀기"],
  ["anki", "Anki 덱 받기"],
  ["bridge", "예습 링크와 크롬 확장"],
  ["help", "문의"],
] as const;

export function GuidePage() {
  return (
    <div className="doc-page guide-page">
      <header className="doc-head">
        <h1>이용방법</h1>
      </header>

      <nav className="guide-toc" aria-label="목차">
        {SECTIONS.map(([id, label]) => (
          <a key={id} href={`#${id}`}>
            {label}
          </a>
        ))}
      </nav>

      <section id="flow">
        <h2>한눈에</h2>
        <p>
          Study_EZ는 강의 한 편마다 <b>강의 전 예습</b>과 <b>강의 후 복습</b>을 준비해 둡니다. 출발점은 언제나
          캘린더이고, 강의 칸을 누르면 아래 단계들이 같은 색으로 서 있습니다.
        </p>
        <StudyFlow />
      </section>

      <section id="calendar">
        <h2>캘린더 읽기</h2>
        <ul>
          <li>
            위쪽의 <b>주 · 월</b>로 보기를 바꾸고, <b>‹ ›</b>로 넘기고, <b>오늘</b>로 돌아옵니다.
          </li>
          <li>칸 왼쪽의 색 띠는 강의 · 실습 · 시험 · 휴일을 구분합니다.</li>
          <li>
            강의 칸에는 자리가 둘 있습니다. <b>왼쪽 동그라미가 예습</b>, <b>오른쪽 네모가 복습</b>입니다.
          </li>
        </ul>
        <dl className="guide-marks">
          <div>
            <dt>
              <i className="chip-slot is-pre is-none" />
              <i className="chip-slot is-main is-none" />
            </dt>
            <dd>
              <b>작은 점</b> — 아직 준비되지 않았습니다.
            </dd>
          </div>
          <div>
            <dt>
              <i className="chip-slot is-pre is-ready" />
              <i className="chip-slot is-main is-ready" />
            </dt>
            <dd>
              <b>빈 도형</b> — 올라왔습니다. 지금 할 수 있는 일입니다. 예습 동그라미는 웹에서 푼 만큼 차오릅니다.
            </dd>
          </div>
          <div>
            <dt>
              <i className="chip-slot is-pre is-done" />
              <i className="chip-slot is-main is-done" />
            </dt>
            <dd>
              <b>채운 도형</b> — 했습니다. 예습은 웹에서 다 풀었거나 덱을 받았을 때, 복습은 덱을 받았을 때
              채워집니다.
            </dd>
          </div>
        </dl>
      </section>

      <section id="panel">
        <h2>강의 칸을 눌렀을 때</h2>
        <p>
          어느 칸이든 누르면 옆에 패널이 열립니다(휴대폰에서는 아래에서 올라옵니다). 캘린더는 그대로 남아 있어서 다른
          칸을 바로 눌러 갈아탈 수 있습니다. 위에서부터 할 일 순서입니다.
        </p>
        <ul>
          <li>
            <b>예습</b> — <b>기본 링크</b>는 반 전체가 같이 읽는 AI 대화이고, <b>개인 링크</b>는 내 프롬프트로 내가
            만든 대화입니다.
          </li>
          <li>
            <b>Pre-Quiz</b> · <b>Main-Quiz</b> — 각각 <b>웹에서 풀기</b>와 <b>덱</b>(Anki 파일)이 나란히
            있습니다. 둘 중 편한 쪽을 쓰면 됩니다.
          </li>
          <li>
            <b>필기</b> — 작년 · 올해 필기 PDF가 새 탭에서 열립니다.
          </li>
          <li>
            아직 만드는 중인 덱은 몇 단계째인지, 몇 분쯤 남았는지가 그 자리에 보입니다. 다 만들어지면 그대로 받을 수
            있습니다.
          </li>
        </ul>
        <p className="guide-note">자료가 하나도 없는 칸은 「아직 올라온 자료가 없습니다」라고 나옵니다. 고장이 아닙니다.</p>
      </section>

      <section id="quiz">
        <h2>웹에서 풀기</h2>
        <p>
          Anki와 같은 방식입니다. 질문을 보고 떠올린 뒤 답을 펴고, 얼마나 잘 기억했는지 스스로 고릅니다. 고른 것에
          따라 그 카드가 다음에 언제 다시 나올지 정해집니다.
        </p>
        <table className="guide-keys">
          <tbody>
            <tr>
              <th>
                <kbd>space</kbd>
              </th>
              <td>답 보기 · 편 뒤에는 Good</td>
            </tr>
            <tr>
              <th>
                <kbd>1</kbd> <kbd>2</kbd> <kbd>3</kbd> <kbd>4</kbd>
              </th>
              <td>Again · Hard · Good · Easy</td>
            </tr>
            <tr>
              <th>
                <kbd>Z</kbd> · <kbd>Ctrl</kbd>+<kbd>Z</kbd>
              </th>
              <td>방금 고른 것 되돌리기</td>
            </tr>
          </tbody>
        </table>
        <ul>
          <li>버튼마다 「1분 · 10분 · 4일」처럼 다음에 다시 나올 때가 적혀 있습니다.</li>
          <li>
            그날 몫을 다 하면 <b>「오늘 몫을 다 했습니다」</b>와 함께 다음 복습 날짜가 나옵니다.
          </li>
          <li>
            시험 직전처럼 일정과 상관없이 전부 한 번 보고 싶으면 <b>지금 몰아서 보기</b>를 누릅니다. 거기서 고른
            것도 똑같이 일정에 반영됩니다.
          </li>
          <li>
            10월 4일 이후 만든 Pre-Quiz는 질문 위에 <b>이 문제를 왜 냈는지</b>의 유형이 배지로 붙고, 답을 펴면
            이유가 한 줄로 나옵니다 — <span className="badge why-exam">기출</span> <span className="badge why-clinical">임상</span>{" "}
            <span className="badge why-later">연결 개념</span> <span className="badge why-annotation">필기 강조</span>{" "}
            <span className="badge why-basis">기본 개념</span>.{" "}
            <span className="badge is-challenge">도전 문제</span> 는 수업에서 답이 나오는 질문이니 못 풀어도 괜찮습니다 —
            수업을 들으며 답을 찾아보세요.
          </li>
        </ul>
      </section>

      <section id="anki">
        <h2>Anki 덱 받기</h2>
        <ul>
          <li>
            패널의 <b>덱</b>을 누르면 <code>.apkg</code> 파일이 받아집니다. 그 파일을 더블클릭하거나 Anki의{" "}
            <b>파일 → 가져오기</b>로 엽니다. 웹 문제에는 없는 그림 카드까지 들어 있습니다.
          </li>
          <li>
            캘린더 맨 아랫줄의 모아받기 버튼은 <b>그날 덱을 한 파일로</b> 받습니다. 예습과 복습이 따로 있습니다.
          </li>
          <li>
            패널 아래쪽의 <b>블럭 덱 받기</b>는 그 과목에서 <b>지금까지 나온 덱</b>을 한 파일로 묶습니다. 앞으로
            나올 편은 나중에 다시 받아야 들어옵니다.
          </li>
        </ul>
      </section>

      <section id="bridge">
        <h2>예습 링크와 크롬 확장</h2>
        <p>
          기본 링크는 누르면 바로 열립니다. <b>개인 링크</b>를 만들려면 컴퓨터의 크롬에 <b>예습 브리지</b> 확장이
          있어야 합니다. 설치 안내는 패널의 예습 칸에 있고, 설치한 뒤에는 그 탭을 새로고침합니다.
        </p>
        <ol>
          <li>
            개인 링크의 <b>만들기</b>를 누르면 고른 AI(ChatGPT · Gemini · Claude)가 열리고, 작년 필기와 예습
            프롬프트가 자동으로 들어갑니다.
          </li>
          <li>
            <b>전송은 직접 누릅니다.</b> 답이 끝나면 대화 주소가 이 강의에 저장됩니다.
          </li>
          <li>
            프롬프트는 <b>프롬프트 수정</b>에서 내 방식대로 고칠 수 있습니다. <b>기본값으로</b>를 누르면 처음 문구로 돌아갑니다.
          </li>
        </ol>
        <p className="guide-note">
          확장이 무엇을 읽고 어디로 보내는지는 <a href="/privacy">개인정보처리방침</a>에 적혀 있습니다.
        </p>
      </section>

      <section id="help">
        <h2>문의</h2>
        <p>
          바뀌는 일정이나 새 기능은 <b>공지사항</b>에 올립니다. 문제가 틀렸거나 화면이 이상하면 관리자에게
          알려 주세요.
        </p>
      </section>
    </div>
  );
}

/**
 * 공부 흐름 한 장(2026-10-04 관리자 — 「이용방법에는 우리의 공부 Flow를
 * 도식화해서 넣어줘.」).
 *
 * **색은 패널의 갈래 색을 그대로 쓴다**(예습 violet · Pre-Quiz teal · Main-Quiz
 * indigo). 그림에서 본 색을 패널에서 다시 만나야 그림이 지도가 된다. 칸의
 * ○ □ 도 같은 이유로 그림 안에 넣었다.
 *
 * 넓은 화면에서는 왼쪽에서 오른쪽으로, 폰에서는 위에서 아래로 흐른다 — 화살표가
 * 같이 돈다(`.flow-arrow`).
 */
function StudyFlow() {
  return (
    <figure className="flow-map">
      <ol className="flow-phases">
        <li className="flow-phase">
          <span className="flow-when">강의 전</span>
          <div className="flow-step is-preview">
            <b>예습</b>
            <span>AI 대화를 읽는다</span>
            <small>기본 링크 · 개인 링크</small>
          </div>
          <span className="flow-down" aria-hidden="true" />
          <div className="flow-step is-pre">
            <b>
              Pre-Quiz <i className="chip-slot is-pre is-ready" aria-label="칸의 동그라미" />
            </b>
            <span>예습 대화로 만든 문제</span>
            <small>웹에서 풀기 · 덱</small>
          </div>
          <span className="flow-source">재료 · 작년 필기</span>
        </li>

        <li className="flow-arrow" aria-hidden="true" />

        <li className="flow-phase">
          <span className="flow-when">수업</span>
          <div className="flow-step is-class">
            <b>강의</b>
            <span>수업을 듣는다</span>
          </div>
          <span className="flow-source">올해 필기가 올라오면 Main-Quiz가 만들어진다</span>
        </li>

        <li className="flow-arrow" aria-hidden="true" />

        <li className="flow-phase">
          <span className="flow-when">강의 후 · 매일</span>
          <div className="flow-step is-main">
            <b>
              Main-Quiz <i className="chip-slot is-main is-ready" aria-label="칸의 네모" />
            </b>
            <span>올해 필기로 만든 문제</span>
            <small>웹에서 풀기 · 덱</small>
            <span className="flow-loop">
              <svg viewBox="0 0 16 16" aria-hidden="true">
                <path d="M13 8a5 5 0 1 1-1.6-3.7" />
                <path d="M11.8 1.8v2.8H9" />
              </svg>
              오늘 낼 카드만 · 잊을 때쯤 다시
            </span>
          </div>
          <span className="flow-source">재료 · 올해 필기</span>
        </li>

        <li className="flow-arrow" aria-hidden="true" />

        <li className="flow-phase">
          <span className="flow-when">시험 전</span>
          <div className="flow-step is-exam">
            <b>몰아보기</b>
            <span>일정과 상관없이 한 바퀴</span>
          </div>
          <span className="flow-down" aria-hidden="true" />
          <div className="flow-step is-exam">
            <b>블럭 덱</b>
            <span>지금까지 나온 덱을 한 파일로</span>
          </div>
        </li>
      </ol>
      <figcaption>
        캘린더 칸의 <i className="chip-slot is-pre is-ready" /> 는 Pre-Quiz, <i className="chip-slot is-main is-ready" /> 는
        Main-Quiz 자리입니다. 웹에서 풀든 덱으로 Anki에서 풀든 같은 문제입니다.
      </figcaption>
    </figure>
  );
}
