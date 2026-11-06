import { useState } from "react";
import { ACCENTS, loadAccent, saveAccent, type AccentId } from "../theme";

/** 설정(2026-11 개편). 지금은 색 조합 하나. 고르면 바로 바뀌고 이 기기에 남는다. */
export function SettingsPage({ email, onSignOut }: { email: string; onSignOut: () => void }) {
  const [accent, setAccent] = useState<AccentId>(loadAccent);
  return (
    <div className="settings-page">
      <header className="page-head">
        <div>
          <h1>설정</h1>
          <p className="page-sub">{email}</p>
        </div>
      </header>

      <section className="settings-section">
        <h2>색 조합</h2>
        <div className="accent-list" role="radiogroup" aria-label="색 조합">
          {ACCENTS.map(a => (
            <button
              key={a.id}
              type="button"
              role="radio"
              aria-checked={a.id === accent}
              className="accent-option"
              onClick={() => {
                setAccent(a.id);
                saveAccent(a.id);
              }}
            >
              <span className="accent-swatch" aria-hidden="true">
                <span style={{ background: a.accent }} />
                <span style={{ background: a.accent2 }} />
              </span>
              <span className="accent-name">{a.name}</span>
            </button>
          ))}
        </div>
      </section>

      <section className="settings-section">
        <h2>계정</h2>
        <button type="button" className="is-quiet" onClick={onSignOut}>로그아웃</button>
      </section>
    </div>
  );
}
