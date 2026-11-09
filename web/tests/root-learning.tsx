import { createRoot } from 'react-dom/client';
import { MemoryRouter,Routes,Route } from 'react-router-dom';
import { RootLearningPage } from '../src/bank/RootLearning';
import { Sidebar } from '../src/shell/Sidebar';
import '../src/styles/base.css';
// Same frame as the site (App.tsx): Main-Quiz stands beside the left menu, so the map's room is the real one.
createRoot(document.getElementById('root')!).render(<MemoryRouter initialEntries={['/bank/test/demo/roots']}>
  <div className="app-shell">
    <Sidebar email="student@studyez.kr" isAdmin={false} unseenNotice={false} onSignOut={()=>{}}/>
    <div className="app-column"><main className="app-main"><Routes>
      <Route path="/bank/:subject/:runId/roots" element={<RootLearningPage/>}/>
    </Routes></main></div>
  </div>
</MemoryRouter>);
