import { Link, useLocation, useNavigate } from "react-router-dom";
import { FeedbackButton } from "./feedback/FeedbackButton";

/** 학습 화면에서도 같은 탭의 방문 기록과 캘린더를 자유롭게 오간다. */
export function StudyNav() {
  const location = useLocation();
  const navigate = useNavigate();
  return <header className="study-nav">
    <nav aria-label="학습 화면 이동">
      <button className="is-quiet" onClick={() => location.key === "default" ? navigate("/") : navigate(-1)}>← 뒤로</button>
      <Link to="/">캘린더</Link>
      <Link to="/study">학습 현황</Link>
    </nav>
    <FeedbackButton />
  </header>;
}
