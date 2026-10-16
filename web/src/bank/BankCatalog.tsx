import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { bankHref, lectureHref } from "../links";
import { SlideImage } from "../SlideImage";
import type { BankCatalog, BankCatalogAnswer, BankCatalogItem } from "../types/bank";
import { AnswerBody, QuestionBody } from "./BankQuestion";
import "./catalog.css";

const formats: Record<string, string> = { basic: "단답", cloze: "빈칸", list: "나열", ox: "O/X",
  mcq: "객관식", multi_select: "복수 선택", matching: "짝짓기", sequence: "순서" };
const tiers: Record<string, string> = { Essential: "★ Must-Know", Core: "Core", Important: "Important", Optional: "Optional" };
const normalize = (text: string) => text.toLocaleLowerCase().replace(/\s+/g, "");
const groupId = (page: number | null) => `catalog-slide-${page ?? "none"}`;

export function BankCatalogPage() {
  const { subject = "", runId = "" } = useParams();
  return <Catalog key={`${subject}/${runId}`} subject={subject} runId={runId} />;
}

function Catalog({ subject, runId }: { subject: string; runId: string }) {
  const base = `/api/lectures/${encodeURIComponent(subject)}/${encodeURIComponent(runId)}/bank/catalog`;
  const [catalog, setCatalog] = useState<BankCatalog | null>(null);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");
  const reload = () => setRevision(value => value + 1);
  useEffect(() => {
    const controller = new AbortController();
    setCatalog(null); setError("");
    void api<BankCatalog>(base, { signal: controller.signal }).then(value => {
      if (!controller.signal.aborted) setCatalog(value);
    }).catch(cause => { if (!controller.signal.aborted) setError((cause as Error).message); });
    return () => controller.abort();
  }, [base, revision]);
  useEffect(() => {
    document.title = `${catalog?.title ? `${catalog.title} · ` : ""}전체 문제 · Study_EZ`;
  }, [catalog?.title]);
  const { groups, count } = useMemo(() => {
    const found = new Map<number | null, { item: BankCatalogItem; number: number }[]>();
    let count = 0;
    for (const [index, item] of (catalog?.questions ?? []).entries()) {
      const q = item.question;
      if ((filter === "active" && item.suspended) || (filter === "suspended" && !item.suspended)
        || (filter === "personal" && !q.personalAdded)) continue;
      if (normalize(search) && !normalize(`${q.question_id} ${q.question}`).includes(normalize(search))) continue;
      const page = item.pages[0] ?? null;
      const rows = found.get(page) ?? [];
      rows.push({ item, number: index + 1 }); found.set(page, rows); count++;
    }
    return { groups: [...found.entries()], count };
  }, [catalog, search, filter]);
  const slides = new Map(catalog?.slides.map(slide => [slide.page, slide.url]));
  return <section className="bank-catalog">
    <header className="catalog-heading">
      <div><p>{subject}{catalog?.title ? ` · ${catalog.title}` : ""}</p><h1>전체 문제</h1>
        <p>슬라이드 순서대로 훑어보세요. 열람해도 학습 기록과 복습 일정은 바뀌지 않습니다.</p></div>
      <div className="catalog-links"><Link to={lectureHref({ subject, runId })}>강의 자료</Link>
        <Link to={bankHref({ subject, runId })}>학습하러 가기 →</Link></div>
    </header>
    {error ? <div role="alert" className="notice is-error">{error} <button onClick={reload}>다시 불러오기</button></div>
      : !catalog ? <p className="notice" role="status">전체 문제를 불러오는 중…</p> : <>
        <div className="catalog-toolbar">
          <label>문제 검색 <input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="문제 내용 · 문항 ID" /></label>
          <label>보기 <select value={filter} onChange={event => setFilter(event.target.value)}>
            <option value="all">모든 문제</option><option value="active">학습 중인 문제</option>
            <option value="suspended">비활성화한 문제</option><option value="personal">내가 추가한 문제</option>
          </select></label>
          <span role="status">{count} / {catalog.questions.length}문항 · 슬라이드 순</span>
          <button className="is-quiet" onClick={reload}>목록 새로고침</button>
        </div>
        <div className="catalog-layout">
          <nav className="catalog-index" aria-label="슬라이드별 문제 이동">
            <strong>슬라이드</strong>{groups.map(([page, rows]) => <a key={page ?? "none"} href={`#${groupId(page)}`}>
              <span>{page === null ? "위치 미지정" : `PDF ${page}쪽`}</span><small>{rows.length}</small>
            </a>)}
          </nav>
          <div className="catalog-groups">
            {groups.map(([page, rows]) => <section key={page ?? "none"} id={groupId(page)} className="catalog-group" aria-labelledby={`${groupId(page)}-title`}>
              <h2 id={`${groupId(page)}-title`}>{page === null ? "슬라이드 위치 미지정" : `PDF ${page}쪽`}<small>{rows.length}문항</small></h2>
              <div className="catalog-group-body">
                <div className="catalog-slide">
                  {page !== null && slides.has(page) ? <SlideImage src={slides.get(page)!} alt={`필기 PDF ${page}쪽`} loading="lazy" />
                    : <p>{page === null ? "슬라이드 위치가 없는 문제입니다." : "등록된 슬라이드 이미지가 없습니다."}</p>}
                  {page !== null ? <small>PDF 쪽 번호 기준 · 여러 쪽을 인용한 문제는 첫 쪽에 표시</small> : null}
                </div>
                <div className="catalog-cards">{rows.map(({ item, number }) => <CatalogCard key={`${catalog.buildId}:${item.question.question_id}`}
                  item={item} number={number} base={base} buildId={catalog.buildId} reload={reload} />)}</div>
              </div>
            </section>)}
            {!count ? <div className="catalog-empty"><p>{catalog.questions.length ? "조건에 맞는 문제가 없습니다." : "등록된 문제가 없습니다."}</p>
              {search || filter !== "all" ? <button onClick={() => { setSearch(""); setFilter("all"); }}>모든 문제 보기</button> : null}</div> : null}
          </div>
        </div>
      </>}
  </section>;
}

function CatalogCard({ item, number, base, buildId, reload }: {
  item: BankCatalogItem; number: number; base: string; buildId: string; reload: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<BankCatalogAnswer | null>(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const qid = item.question.question_id;
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    setError(""); setDetail(null);
    void api<BankCatalogAnswer>(`${base}/${encodeURIComponent(qid)}?buildId=${encodeURIComponent(buildId)}`,
      { signal: controller.signal }).then(value => {
      if (!controller.signal.aborted) setDetail(value);
    }).catch(cause => { if (!controller.signal.aborted) setError((cause as Error).message); });
    return () => controller.abort();
  }, [open, base, qid, buildId, retry]);
  const q = detail?.question ?? item.question;
  const answer = open ? detail?.answer ?? null : null;
  const answerId = `catalog-answer-${qid}`;
  return <article className="catalog-card" aria-label={`${number}번 문제`}>
    <header><span className="catalog-number">{number.toString().padStart(2, "0")}</span>
      <span>{formats[q.format] ?? q.format}</span><span className={q.tier === "Essential" ? "catalog-essential" : ""}>{tiers[q.tier] ?? q.tier}</span>
      {q.advanced ? <span>심화</span> : null}{q.personalAdded ? <span>내 문제</span> : q.personalEdited ? <span>내 수정본</span> : null}
      {item.suspended ? <span>비활성화</span> : null}<small>{qid}</small></header>
    <QuestionBody question={q} answer={answer} picked={new Set()} onPick={() => {}} disabled showChoiceScore={false} />
    {item.pages.length > 1 ? <p className="bank-note">참고 쪽: {item.pages.join(", ")}</p> : null}
    <button type="button" className="catalog-reveal" aria-expanded={open} aria-controls={answerId}
      onClick={() => setOpen(value => !value)}>{open ? "정답·해설 접기 ↑" : "정답·해설 보기 ↓"}</button>
    <div id={answerId} hidden={!open} className="catalog-answer">
      {open && (error ? <div className="notice is-error" role="alert">{error}<div>
        <button onClick={() => setRetry(value => value + 1)}>다시 시도</button> <button onClick={reload}>목록 새로고침</button>
      </div></div> : answer ? <AnswerBody question={q} answer={answer} /> : <p role="status">정답·해설을 불러오는 중…</p>)}
    </div>
  </article>;
}
