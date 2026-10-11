import "../styles/learning.css";

/** Shared by the study dashboard and the usage guide. */
export function LearningOverview() {
  return <section className="learning-overview" aria-label="전체 학습 흐름">
    <span className="learning-eyebrow">공부는 이렇게 이어져요</span>
    <h2>오늘 학습 → 간격 복습 → 시험 연습</h2>
    <p>강의에서 알아야 할 내용을 ‘학습요점’으로 나눠 공부합니다. 학습요점은 기억해야 할 내용 하나예요.</p>
    <ol className="learning-roadmap">
      <li><span className="learning-step-number" aria-hidden="true">1</span><div><h3>오늘 학습부터 시작</h3><p>하루 공부 시간 안에서 여러 강의의 새 내용과 복습을 함께 공부해요.</p></div></li>
      <li><span className="learning-step-number" aria-hidden="true">2</span><div><h3>시간을 두고 다시 기억</h3><p>정답을 확인한 뒤 실제로 기억한 정도를 평가해요. 어렵게 맞힌 답도 성공이며, 평가에 따라 다음 복습을 잡습니다.</p></div></li>
      <li><span className="learning-step-number" aria-hidden="true">3</span><div><h3>처음 보는 문제로 확인</h3><p>배운 범위의 새 객관식으로 시험 연습을 해요. 정답과 해설은 연습을 마친 뒤 볼 수 있어요.</p></div></li>
    </ol>
    <p className="learning-overview-note"><strong>더 공부하고 싶다면 추가 학습.</strong> 원하는 강의를 더 볼 수 있고, 오늘 완료한 분량은 유지됩니다.</p>
    <details className="learning-overview-more"><summary>자료·예습·기존 풀이는 어디에 있나요?</summary>
      <p>캘린더에서 강의 자료와 예습 대화·Pre-Quiz를 찾을 수 있어요. 강의 전에 내용을 접하고, 강의 후에는 오늘 학습으로 이어가세요.</p>
      <p>오늘 학습도 정답 확인 후 기억한 정도를 평가합니다. 정답 전 확신 기록은 선택 사항이에요. Anki에서 공부한 기록은 오늘 학습에 자동 합산되지 않습니다.</p>
    </details>
  </section>;
}
