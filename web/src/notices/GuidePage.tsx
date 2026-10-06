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
        <p>
          상단의 <b>학습도</b> 탭에서 오늘의 학습 목표와 강의별 학습도를 확인합니다.
          <b>시험까지 오늘의 학습 목표</b>는 시험 범위의 예정 강의를 미리 포함하고, 목표까지 필요한 순증가분과
          오늘의 예상 망각분을 더해 오늘 확보할 학습량을 제시합니다. 기본 시험 목표는 90%이며 직접 바꿀 수 있습니다.
          시험 3일 전까지 목표에 도달하고 마지막 3일은 복습과 밀린 분량에 쓰도록 계획합니다.
          망각 보충을 포함한 하루 확보량을 고르게 잡아 초반 순증가 목표가 더 높습니다. 실제 공부 시간을 보장하는 값은 아닙니다.
          하루 목표는 한국 자정의 기록을 기준으로 정하고 공부한 만큼 남은 분량이 줄어듭니다.
          시험 범위는 같은 과목의 다음 시험까지로 추정하며, 문제가 준비되지 않은 강의는 계획상 0%로 가정합니다.
        </p>
        <p>
          <b>강의별 학습도</b>에서는 오늘까지의 강의 중 학습이 부족한 강의를 낮은 점수부터 보여 줍니다.
          Quiz Bank의 핵심 개념마다 회상 방향별 숙련도를 목표와 비교하고, 학습이 부족한 개념을 더 크게 반영합니다.
          몇 개념만 완벽히 아는 것보다 여러 개념을 고르게 아는 편이 높은 점수를 받습니다.
          예를 들어 두 개념의 목표 달성도가 각각 100%·0%이면 강의 학습도는 29%, 50%·50%이면 50%입니다. 모든 핵심 개념이
          목표에 도달하면 <b>목표 달성</b>입니다. 핵심 문항이 없는 은행은 전체 개념을 기준으로 합니다.
          <b>미학습</b>과 문제가 아직 없는 <b>평가 준비 전</b>을 구분하며, Anki·기존 카드 기록은 포함하지 않습니다.
          <b>학습하기</b>로 바로 풀 수 있고, 학습도 탭으로 돌아오면 점수가 갱신됩니다.
          학습도는 마지막 평가 이후 시간이 지나면 망각곡선에 따라 감소하는 추정치입니다.
          간격을 두고 Good·Easy로 평가하면 기억 유지 기간이 늘어나고, Again이면 짧아집니다.
          짧은 시간의 반복은 현재 숙련도를 올릴 수 있지만 기억 유지 기간은 늘리지 않습니다.
          과거 회차의 결과는 당시 값으로 보존됩니다.
        </p>
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
              <b>빈 도형</b> — 올라왔습니다. 지금 할 수 있는 일입니다. 예습 동그라미는 도전문제를 포함한
              풀이 비율에 따라 왼쪽부터 초승달 · 반달 · 보름달처럼 차오르며, 다 풀어도 파란색을 유지합니다.
              관리자도 자신의 예습 진행률을 봅니다.
            </dd>
          </div>
          <div>
            <dt>
              <i className="chip-slot is-pre is-done" />
            </dt>
            <dd>
              <b>채운 동그라미</b> — 예습을 웹에서 다 풀었습니다. 웹 문항이 없는 덱은 내려받으면 채워집니다.
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
            <b>Pre-Quiz</b> — 웹에서 풀거나 Anki 덱으로 학습합니다.
          </li>
          <li>
            <b>Main-Quiz</b> — 공개된 Quizbank 문제를 웹에서 풉니다. 회차마다 개념별 숙련도와 시험일까지
            남은 날에 따라 다음 문제가 선택됩니다. 예전 카드와 Anki 덱은 <b>기존 Main-Quiz 자료</b>에서 열 수 있습니다.
          </li>
          <li>
            <b>필기</b> — 작년 · 올해 필기 PDF가 새 탭에서 열립니다.
          </li>
          <li>
            아직 만드는 중인 덱은 몇 단계째인지, 몇 분쯤 남았는지가 그 자리에 보입니다. 다 만들어지면 그대로 받을 수
            있습니다.
          </li>
        </ul>
        <p className="guide-note">Main-Quiz의 빈 네모는 공개된 문제은행이 있다는 뜻입니다. 회차별 학습 결과는 풀이 화면에서 확인합니다.</p>
      </section>

      <section id="quiz">
        <h2>웹에서 풀기</h2>
        <p>
          <b>Main-Quiz</b>는 문항 수를 정하지 않고 바로 시작합니다. 원하면 문항 수 제한을 설정할 수 있습니다. 답과 근거 슬라이드를 확인한 뒤
          Again · Hard · Good · Easy로 평가합니다. 원할 때 회차를 마칠 수 있고, 지금 낼 문제가 없으면 자동으로 마칩니다. 종료 후 개념별 숙련도와 남은 약점을 확인하고
          한 회차 더 풀 수 있습니다.
        </p>
        <p>
          풀이 화면에는 <b>전체 중 완료한 수와 남은 수</b>를 표시합니다. 상단 진행 현황은 처음에는 접혀 있으며 누르면 상세 내용을 펼칠 수 있습니다.
          핵심 개념과 회상 방향을 한 학습 단위로 세며 필요한 선행 내용도 포함합니다.
          처음에는 각 단위를 확인하고, 이후에는 오늘 복습 예정인 단위를 학습합니다.
          Good·Easy는 오늘 완료, Again·Hard는 잠시 뒤 다시 확인합니다. 대기 중인 재학습이 있으면 아직 완료되지 않습니다.
          남은 단위가 0이 되면 자동으로 회차를 마치고 「오늘 학습할 내용을 완료하였습니다!」 화면을 표시합니다.
          「메인으로 돌아가기」로 마무리하거나, 현재 강의를 더 공부할 수 있습니다.
          숙련도와 달력의 시험 대비 계획은 별도 지표입니다. 한국 자정에 새 하루가 시작됩니다.
        </p>
        <h3>Pre-Quiz</h3>
          <p>
            새 Pre-Quiz는 핵심 5문항과 도전 1문항 이내로 구성됩니다. 막히면 힌트를 열어
            다시 생각해 보세요. 답을 편 뒤에는 출제 이유, 지금 알아둘 범위, 수업에서 들을 질문을
            확인합니다. 이해가 덜 된 내용은 「아직 헷갈려요」, 이해한 내용은 「이해했어요」를 누르면 다음 문항으로 넘어갑니다.
            예습을 마치면 「아직 헷갈려요」를 고른 문제의 질문·답·설명을 바로 보여줍니다.
            「어려웠던 문제만 다시 풀기」로 그 문제들만 다시 확인할 수 있으며, 수업에서 확인할 내용도 함께 표시합니다.
            예습에는 다음 복습 일정을 잡지 않습니다.
            도전 문제는 문항 뱃지로 표시하며 같은 방식으로 풉니다. 전체 문제 수와 완료 수에도 포함되고,
            캘린더의 예습 동그라미가 완료한 비율만큼 달처럼 차오릅니다.
            Anki에서는 도전 문제 태그와 안내를 확인하고 필요할 때 풀면 됩니다.
          </p>
        <table className="guide-keys">
          <tbody>
            <tr><th><kbd>Space</kbd> · <kbd>Enter</kbd></th><td>답과 설명 보기 · 편 뒤에는 이해했어요</td></tr>
            <tr><th><kbd>1</kbd> · <kbd>2</kbd></th><td>아직 헷갈려요 · 이해했어요</td></tr>
            <tr><th><kbd>Z</kbd> · <kbd>Ctrl</kbd>+<kbd>Z</kbd></th><td>이전 선택 되돌리기</td></tr>
          </tbody>
        </table>
        <h3>기존 Main-Quiz 카드</h3>
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
        <p>Pre-Quiz와 Quiz Bank 기반 Main-Quiz를 Anki 덱으로 받을 수 있습니다.</p>
        <ul>
          <li>
            패널의 <b>덱</b>을 누르면 <code>.apkg</code> 파일이 받아집니다. 그 파일을 더블클릭하거나 Anki의{" "}
            <b>파일 → 가져오기</b>로 엽니다. Main-Quiz의 <b>Anki 덱 받기</b>는 Quiz Bank 전체 문항과 정답,
            근거 슬라이드를 담습니다. Anki와 웹의 학습 기록·복습 일정은 각각 관리됩니다.
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
            예습의 <b>개인 링크</b> 카드를 누르면 고른 AI(ChatGPT · Gemini · Claude)가 열립니다.
            작년 필기와 올해 강의에 연결된 족보(있는 경우), 예습 프롬프트를 함께 넣습니다.
          </li>
          <li>
            개인 링크는 확장 카드에서 자료와 프롬프트를 확인한 뒤 직접 전송합니다. 기본 링크의 <b>자동전송</b>은 관리자에게만 보입니다.
            Main-Quiz 앞의 <b>복습 개인 링크</b>는 올해 강의록으로 만듭니다. 생성 칸은 처음에는 접혀 있으며
            <b>복습</b>을 눌러 펼칩니다. 저장된 복습 대화는 바로 열 수 있습니다.
            <b>ChatGPT로 만들기</b>는 Main-Quiz 문제를 만들며, 답이 끝나면 링크 또는 문제가 각각 저장됩니다.
            전송 전 확장 카드의 ×를 누르면 중지합니다.
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
          화면 오른쪽 위의 <b>피드백</b>으로 알려 주세요. 캡처 파일을 선택하거나 붙여넣기·끌어 놓기로
          최대 3장까지 첨부할 수 있습니다(한 장당 3MB). 보고 있던 화면도 함께 전달됩니다.
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
          <span className="flow-source">올해 필기로 출제하고 검증한 문제를 관리자가 공개한다</span>
        </li>

        <li className="flow-arrow" aria-hidden="true" />

        <li className="flow-phase">
          <span className="flow-when">강의 후 · 매일</span>
          <div className="flow-step is-main">
            <b>
              Main-Quiz <i className="chip-slot is-main is-ready" aria-label="칸의 네모" />
            </b>
            <span>올해 필기로 만든 문제</span>
            <small>Quizbank · 웹에서 풀기</small>
            <span className="flow-loop">
              <svg viewBox="0 0 16 16" aria-hidden="true">
                <path d="M13 8a5 5 0 1 1-1.6-3.7" />
                <path d="M11.8 1.8v2.8H9" />
              </svg>
              개념별 숙련도에 따라 다음 문제
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
        Main-Quiz 자리입니다. Main-Quiz는 공개된 Quizbank가 있으면 표시됩니다.
      </figcaption>
    </figure>
  );
}
