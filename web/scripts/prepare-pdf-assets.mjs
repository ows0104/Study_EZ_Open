import { cpSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
const web=new URL('../',import.meta.url);
for(const folder of ['cmaps','standard_fonts','wasm']){
  const target=fileURLToPath(new URL(`public/pdfjs/${folder}`,web));
  mkdirSync(target,{recursive:true});
  cpSync(fileURLToPath(new URL(`node_modules/pdfjs-dist/${folder}`,web)),target,{recursive:true});
}
