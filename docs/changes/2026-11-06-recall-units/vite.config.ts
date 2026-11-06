import original from '../../../web/vite.config';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
const root=fileURLToPath(new URL('.',import.meta.url));
const repo=fileURLToPath(new URL('../../../',import.meta.url));
const data=fileURLToPath(new URL('../../../../../runs/_recall/261106/comparison-data.json',import.meta.url));
export default (env:Parameters<typeof original>[0])=>({...original(env),root,plugins:[...original(env).plugins,{name:'local-comparison-data',configureServer(server:any){server.middlewares.use('/comparison-data.json',(_req:any,res:any)=>{try{res.setHeader('Content-Type','application/json; charset=utf-8');res.setHeader('Cache-Control','no-store');res.end(readFileSync(data));}catch{res.statusCode=503;res.end('{}');}});}}],
  cacheDir:fileURLToPath(new URL('../../../../../runs/_recall/261106/vite-cache',import.meta.url)),
  resolve:{dedupe:['react','react-dom'],alias:{'react-dom':repo+'web/node_modules/react-dom','react':repo+'web/node_modules/react'}},server:{host:'127.0.0.1',port:5197,strictPort:true,fs:{allow:[repo]}}});
