import { createRoot } from 'react-dom/client';
import { MemoryRouter,Routes,Route } from 'react-router-dom';
import { RootLearningPage } from '../src/bank/RootLearning';
import '../src/styles/base.css';
createRoot(document.getElementById('root')!).render(<MemoryRouter initialEntries={['/bank/test/demo/roots']}><Routes>
  <Route path="/bank/:subject/:runId/roots" element={<RootLearningPage/>}/>
</Routes></MemoryRouter>);
