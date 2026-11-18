import { createRoot } from 'react-dom/client';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { JokboMixPage } from '../src/jokbo/JokboMix';
import { Sidebar } from '../src/shell/Sidebar';
import '../src/styles/base.css';
// Same frame as the site (App.tsx): 족보 모아풀기 beside the left menu.
const start = '/study/jokbo-mix' + (location.search || '?e=evA&e=evB&e=evC');
createRoot(document.getElementById('root')!).render(<MemoryRouter initialEntries={[start]}>
  <div className="app-shell">
    <Sidebar email="student@studyez.kr" isAdmin={false} unseenNotice={false} onSignOut={() => {}} />
    <div className="app-column"><main className="app-main"><Routes>
      <Route path="/study/jokbo-mix" element={<JokboMixPage />} />
      <Route path="/study" element={<h1>강의 목록</h1>} />
    </Routes></main></div>
  </div>
</MemoryRouter>);
