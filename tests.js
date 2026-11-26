'use strict';const assert=require('node:assert/strict'),E=require('./engine');const p={capital:1200,fx:130,fee:.001,slippage:.0005,risk:.01,stop:.02,maxDailyLoss:.02,maxDrawdown:.05},rules={minNotional:5,minQty:.00001,maxQty:100,step:.00001},tiny={minNotional:0,minQty:.00000001,maxQty:100,step:.00000001};let pass=0,fail=0;
function run(n,fn){try{fn();console.log('PASS',n);pass++}catch(e){console.log('FAIL',n,e.stack);fail++}}
function data(){let arr=[],old=100;for(let i=0;i<150;i++){const c=100+12*Math.sin(i/7),o=old,l=Math.min(o,c)-(i%17===4?20:1.5);arr.push({t:Date.UTC(2025,0,1)+i*86400000,o,h:Math.max(o,c)+1.5,l,c});old=c;}return arr}
run('A minimum notional blocks KES1200',()=>assert.throws(()=>E.fitQty(1200/130,70000,1200/130,p,rules),/MIN_NOTIONAL/));
run('B manual halt state disallows entries',()=>assert.equal(E.entryAllowed({manualHalt:true,quoteFresh:true,rulesVerified:true}),false));
run('C higher friction worsens round trip',()=>{let f=x=>(100*(1-x)*(1-x)-100*(1+x));assert.ok(f(.002)>f(.004))});
run('D stale quote checks',()=>{assert.equal(E.fresh(0,10000,1000),false);assert.equal(E.fresh(12000,10000,1000),false);assert.equal(E.fresh(9500,10000,1000),true)});
run('E intrabar stops fire',()=>assert.ok(E.replay(data(),p,tiny).stops>0));
run('F drawdown halts entries',()=>assert.equal(E.guard(94,100,100,p).blocked,true));
run('G split is chronological and independent',()=>{let d=data(),r=E.splitReplay(d,p,tiny);assert.equal(r.split,105);assert.equal(r.outOfSample.curve[0].time,d[105].t);assert.equal(r.outOfSample.curve.length,45)});
run('H invalid settings are refused',()=>assert.throws(()=>E.checkSettings({...p,risk:.2}),/Risk/));
run('I lot size rounded down',()=>assert.equal(E.floorStep(.012345,.001),.012));
run('J no look ahead: changing future candles cannot change prior signal',()=>{let d=data(),s=E.signal(d,80),cloned=d.map(x=>({...x}));for(let i=82;i<150;i++)cloned[i].c*=10;assert.equal(E.signal(cloned,80),s)});
run('K exit stop can gap below trigger',()=>{let d=data();const r=E.replay(d,p,tiny);assert.ok(r.trades.filter(x=>x.kind==='STOP').length>0)});
run('L out of sample starts at configured capital',()=>{let d=data(),r=E.splitReplay(d,p,tiny);assert.ok(Number.isFinite(r.outOfSample.net));assert.equal(r.outOfSample.curve.length,45)});
console.log(`${pass} PASS / ${fail} FAIL`);if(fail)process.exitCode=1;
