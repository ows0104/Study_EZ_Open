import { createRoot } from 'react-dom/client';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ConnectionLearningPage } from '../src/bank/ConnectionLearning';
import '../src/styles/base.css';

createRoot(document.getElementById('root')!).render(<MemoryRouter initialEntries={['/bank/test/demo/connections']}><Routes>
  <Route path="/bank/:subject/:runId/connections" element={<ConnectionLearningPage/>}/>
</Routes></MemoryRouter>);
