// node crime/render.js ep.json timeline.json framesDir
const {chromium}=require('playwright');const fs=require('fs');const path=require('path');const http=require('http');
const [ep,tl,outd]=process.argv.slice(2);fs.mkdirSync(outd,{recursive:true});
const root=path.resolve(__dirname);const types={'.html':'text/html','.js':'text/javascript','.json':'application/json'};
const srv=http.createServer((q,r)=>{let f=q.url==='/ep.json'?path.resolve(ep):path.join(root,decodeURIComponent(q.url.split('?')[0]));
 if(q.url==='/three.module.js')f=path.join(path.dirname(require.resolve('three')),'three.module.js');
 fs.readFile(f,(e,d)=>{if(e){r.writeHead(404);return r.end()}r.writeHead(200,{'Content-Type':types[path.extname(f)]||'application/octet-stream'});r.end(d)})}).listen(8787);
(async()=>{const b=await chromium.launch({args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 const p=await b.newPage({viewport:{width:720,height:1280}});p.on('pageerror',e=>console.log('ERR',e.message));
 await p.goto('http://localhost:8787/crime.html');await p.evaluate(()=>load('/ep.json'));const T0=JSON.parse(fs.readFileSync(tl));await p.evaluate(T=>setCaps(T),T0);
 const T=JSON.parse(fs.readFileSync(tl));let k=0;
 for(let i=0;i<T.length;i++){const n=Math.round(T[i].dur*24);
  for(let f=0;f<n;f++){const t=f/24;await p.evaluate(([i,t,talk])=>renderAt(i,t,talk),[i,t,t>=T[i].talk0&&t<=T[i].talk1]);
   await p.screenshot({path:`${outd}/f${String(k++).padStart(5,'0')}.jpg`,type:'jpeg',quality:92})}
  console.log('shot',i+1,'/',T.length)}
 await b.close();srv.close()})();
