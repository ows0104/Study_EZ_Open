import { createRoot } from 'react-dom/client';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { RootBatchPage } from '../src/bank/RootBatch';
import { Sidebar } from '../src/shell/Sidebar';
import '../src/styles/base.css';
// Same frame as the site (App.tsx): 모아풀기 stands beside the left menu like the single-lecture Main-Quiz.
const start = '/study/mix' + (location.search || '?l=test/demo&l=test/demo2');
createRoot(document.getElementById('root')!).render(<MemoryRouter initialEntries={[start]}>
  <div className="app-shell">
    <Sidebar email="student@studyez.kr" isAdmin={false} unseenNotice={false} onSignOut={() => {}} />
    <div className="app-column"><main className="app-main"><Routes>
      <Route path="/study/mix" element={<RootBatchPage />} />
      <Route path="/study" element={<h1>강의 목록</h1>} />
      <Route path="/bank/:subject/:runId" element={<h1>강의 하나</h1>} />
    </Routes></main></div>
  </div>
</MemoryRouter>);
