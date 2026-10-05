import { useState } from "react";
import { api } from "../api";
import type { AdminOverview } from "../types/admin";

/**
 * 시간표의 과목 이름과 필기 폴더 이름을 잇는다.
 *
 * 시간표는 "질병의 병리학적 이해"라 쓰고 폴더는 "병리학"이다. 어느 쪽도
 * 상대를 유추할 수 없어서 사람이 한 번 이어 준다.
 */
export function CourseAliases({ overview, onChanged }: { overview: AdminOverview; onChanged: () => void }) {
  const [draft, setDraft] = useState<Record<string, string>>(() =>
    Object.fromEntries(overview.courseAliases.map((alias) => [alias.courseKey, alias.subject])),
  );
  const [saving, setSaving] = useState(false);

  return (
    <section className="admin-aliases">
      <h2>과목 이름 잇기</h2>
      <p className="admin-summary">
        이어 두면 한 교시에 여러 과목이 열릴 때 매칭이 확실해집니다. 비우고 저장하면 연결이 지워집니다.
      </p>
      <table className="admin-table">
        <thead>
          <tr>
            <th>시간표</th>
            <th>필기 폴더</th>
          </tr>
        </thead>
        <tbody>
          {overview.timetableCourses.map((course) => (
            <tr key={course.courseKey}>
              <td>
                {course.course}
                <small>{course.sessions}회</small>
              </td>
              <td>
                <input
                  list="studyez-subjects"
                  value={draft[course.courseKey] ?? ""}
                  placeholder="예: 병리학"
                  onChange={(event) =>
                    setDraft((current) => ({ ...current, [course.courseKey]: event.target.value }))
                  }
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <datalist id="studyez-subjects">
        {overview.subjects.map((subject) => (
          <option key={subject} value={subject} />
        ))}
      </datalist>
      <button
        disabled={saving}
        onClick={async () => {
          setSaving(true);
          try {
            const labels = new Map(overview.timetableCourses.map((course) => [course.courseKey, course.course]));
            await api("/api/admin/course-aliases", {
              method: "PUT",
              body: JSON.stringify(
                Object.entries(draft).map(([courseKey, subject]) => ({
                  courseKey,
                  course: labels.get(courseKey) ?? "",
                  subject: subject.trim(),
                })),
              ),
            });
            onChanged();
          } finally {
            setSaving(false);
          }
        }}
      >
        {saving ? "저장 중…" : "저장"}
      </button>
    </section>
  );
}
