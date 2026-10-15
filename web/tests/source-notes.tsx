import React from "react";
import { createRoot } from "react-dom/client";
import { AnswerBody, QuestionBody } from "../src/bank/BankQuestion";
import type { BankAnswer, BankQuestion } from "../src/types/bank";
import fixture from "./source-notes-fixture.json";
import "../src/styles/base.css";
import "../src/bank/source-notes.css";

const q = fixture.question as BankQuestion;
const answer = fixture.answer as BankAnswer;
createRoot(document.getElementById("root")!).render(<div className="quiz">
  <p className="quiz-progress bank-progress"><span>1 / 10</span><span className="bank-tags">{q.tier} · O/X{q.conflict_id ? <span className="bank-source-badge">자료 간 차이</span> : null}</span></p>
  <QuestionBody question={q} answer={answer} picked={new Set()} onPick={() => {}} />
  <div className="bank-question-actions"><a className="quiz-fix" href="#">공용 문제 수정</a><button className="is-quiet">수정·제보</button></div>
  <hr className="quiz-line" />
  <AnswerBody question={q} answer={answer} />
</div>);
