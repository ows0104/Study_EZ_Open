import {useState} from 'react';
import {createRoot} from 'react-dom/client';
import {MemoryRouter} from 'react-router-dom';
import {RootGenerationPanel} from '../src/bank/RootGenerationPanel';
import '../src/styles/base.css';
function Fixture(){const [count,setCount]=useState(0);return <MemoryRouter><main style={{maxWidth:500,margin:'0 auto'}}><RootGenerationPanel subject="test" runId="demo" onPublished={()=>setCount(v=>v+1)}/><output aria-label="자료 갱신 횟수">{count}</output></main></MemoryRouter>;}
createRoot(document.getElementById('root')!).render(<Fixture/>);
