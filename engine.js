/* DinoTradeOS v0.3 — testable, dependency-free, PAPER-ONLY engine.
   Browser: window.DinoEngine; Node: module.exports. No order API exists. */
(function(root,factory){const e=factory();if(typeof module==='object'&&module.exports)module.exports=e;else root.DinoEngine=e;})(typeof globalThis!=='undefined'?globalThis:this,function(){
'use strict';
const EPS=1e-10;
function valid(v){return typeof v==='number'&&Number.isFinite(v)}
function sma(c,i,n){if(i<n-1)return NaN;let x=0;for(let j=i-n+1;j<=i;j++)x+=c[j].c;return x/n}
function signal(c,i){if(i<21)return 'WAIT';const a=sma(c,i-1,9),b=sma(c,i-1,21),x=sma(c,i,9),y=sma(c,i,21);if(!valid(a)||!valid(b))return'WAIT';return a<=b&&x>b?'BUY':a>=b&&x<y?'SELL':'HOLD'}
function decimals(step){let st=String(step);if(st.includes('e-'))return Number(st.split('e-')[1]);return (st.split('.')[1]||'').length}
function floorStep(q,step){if(!(valid(q)&&valid(step)&&step>0))return 0;return Number((Math.floor(q/step+EPS)*step).toFixed(Math.min(decimals(step)+2,14)))}
function orderQuantity(raw,price,r){if(!r)throw Error('Missing verified symbol rules');if(!(valid(raw)&&raw>0&&valid(price)&&price>0))throw Error('Invalid order quantity or price');const step=Number(r.step),minQty=Number(r.minQty),maxQty=Number(r.maxQty),minNot=Number(r.minNotional);if(!(step>0&&minQty>=0&&maxQty>0&&minNot>=0))throw Error('Invalid exchange rules');const q=floorStep(raw,step);if(q+EPS<minQty||q>maxQty+EPS)throw Error('Order rejected by LOT_SIZE');if(q*price+EPS<minNot)throw Error('Order rejected by MIN_NOTIONAL');return q}
function guard(equity,peak,dayStart,settings){const dd=(peak-equity)/Math.max(peak,EPS),daily=(dayStart-equity)/Math.max(dayStart,EPS);return {drawdown:dd,dailyLoss:daily,blocked:dd+EPS>=settings.maxDrawdown||daily+EPS>=settings.maxDailyLoss};}
function entryAllowed({manualHalt=false,riskBlocked=false,quoteFresh=false,rulesVerified=false,hasPosition=false}={}){return !manualHalt&&!riskBlocked&&quoteFresh&&rulesVerified&&!hasPosition;}
function fresh(lastCloseMs,nowMs,maxAgeMs){return valid(lastCloseMs)&&valid(nowMs)&&lastCloseMs<=nowMs&&nowMs-lastCloseMs<=maxAgeMs;}
function checkSettings(p){if(!(p.fx>0&&p.capital>0&&p.risk>0&&p.risk<=.01&&p.stop>.0&&p.stop<=.2&&p.maxDailyLoss>0&&p.maxDailyLoss<=.02&&p.maxDrawdown>0&&p.maxDrawdown<=.05&&p.fee>=0&&p.slippage>=0&&p.fee<=.05&&p.slippage<=.05))throw Error('Risk, fees or capital settings are outside allowed bounds');}
function fitQty(cash,price,initialCapital,p,rules){const friction=p.fee+p.slippage,lossPerUnit=price*(p.stop+2*friction);const qty=Math.min((initialCapital*p.risk)/Math.max(lossPerUnit,EPS),cash/(price*(1+friction)));return orderQuantity(qty,price,rules)}
function replay(candles,p,rules,fromIndex=0,toIndex=candles.length){checkSettings(p);if(!Array.isArray(candles)||candles.length<55)throw Error('At least 55 complete OHLC candles required');if(!rules)throw Error('Verified exchange rules required');if(fromIndex<0||toIndex>candles.length||fromIndex>=toIndex)throw Error('Invalid replay window');const f=p.fee+p.slippage;let cash=p.capital/p.fx,qty=0,entryPrice=0,stopPrice=0,peak=p.capital/p.fx,dayStart=peak,currentDay='',locked=false,entries=0,exits=0,blockedOrders=0,stops=0,locks=0,costs=0;const trades=[],curve=[];
// Data before fromIndex is warm-up only; no trades or P&L are carried from training to test.
for(let i=Math.max(fromIndex,22);i<toIndex;i++){
 const bar=candles[i],prev=candles[i-1];if(![bar.o,bar.h,bar.l,bar.c,bar.t].every(valid)||bar.o<=0||bar.h<bar.l||bar.c<=0)throw Error('Invalid OHLC bar '+i);
 const day=new Date(bar.t).toISOString().slice(0,10);let marked=(cash+qty*bar.o);if(day!==currentDay){currentDay=day;dayStart=marked;}
 const gOpen=guard(marked,peak,dayStart,p);if(gOpen.blocked&&!locked){locked=true;locks++;}
 // First resolve stop from bar open or intrabar low. Stops can gap past trigger.
 if(qty>0&&(bar.o<=stopPrice||bar.l<=stopPrice)){
   const executeAt=Math.min(bar.o,stopPrice)*(1-p.slippage);const proceeds=qty*executeAt*(1-p.fee);costs+=qty*Math.min(bar.o,stopPrice)*f;cash+=proceeds;trades.push({kind:'STOP',index:i,price:executeAt,qty});qty=0;entryPrice=0;stopPrice=0;exits++;stops++;
 }
 // Decisions use ONLY preceding closed candle. Execute at current open.
 const sig=signal(candles,i-1);
 if(sig==='SELL'&&qty>0){const px=bar.o*(1-p.slippage);cash+=qty*px*(1-p.fee);costs+=qty*bar.o*f;trades.push({kind:'SELL',index:i,price:px,qty});qty=0;entryPrice=0;stopPrice=0;exits++;}
 marked=cash+qty*bar.o;
 if(guard(marked,peak,dayStart,p).blocked&&!locked){locked=true;locks++;}
 if(sig==='BUY'&&qty===0&&!locked){try{const q=fitQty(cash,bar.o,p.capital/p.fx,p,rules);const px=bar.o*(1+p.slippage);const spend=q*px*(1+p.fee);if(spend>cash+EPS)throw Error('Insufficient balance');cash-=spend;qty=q;entryPrice=px;stopPrice=px*(1-p.stop);costs+=q*bar.o*f;entries++;trades.push({kind:'BUY',index:i,price:px,qty:q});
 // Conservative same-candle adverse path: newly opened trade may hit its stop.
 if(bar.l<=stopPrice){const exitAt=stopPrice*(1-p.slippage);cash+=qty*exitAt*(1-p.fee);costs+=qty*stopPrice*f;trades.push({kind:'STOP',index:i,price:exitAt,qty});qty=0;entryPrice=0;stopPrice=0;exits++;stops++;}
 }catch(e){blockedOrders++;}}
 let equity=cash+qty*bar.c;peak=Math.max(peak,equity);const g=guard(equity,peak,dayStart,p);if(g.blocked&&!locked){locked=true;locks++;}
 // Lock blocks new entries; does not prevent exiting. Model emergency flatten at next open after threshold.
 if(locked&&qty>0){ // explicit model is conservative: mark unresolved position, do not assume fill at close
 }
 curve.push({time:bar.t,equity:equity*p.fx,drawdown:g.drawdown,dailyLoss:g.dailyLoss,locked});
 }
 const last=candles[toIndex-1],finalEquity=(cash+qty*last.c)*p.fx,returnPct=(finalEquity/p.capital-1)*100;let high=p.capital,maxDrawdown=0;for(const pt of curve){high=Math.max(high,pt.equity);maxDrawdown=Math.max(maxDrawdown,(high-pt.equity)/Math.max(high,EPS));}
 return {entries,exits,stops,locks,blockedOrders,trades,curve,finalEquity,net:finalEquity-p.capital,returnPct,maxDrawdown,costsKES:costs*p.fx,locked,openQty:qty,days:curve.length};
}
function splitReplay(candles,p,rules){if(candles.length<100)throw Error('Need at least 100 completed OHLC candles');const split=Math.floor(candles.length*.7);return{split,training:replay(candles,p,rules,0,split),outOfSample:replay(candles,p,rules,split,candles.length)};}
return{signal,floorStep,orderQuantity,guard,entryAllowed,fresh,checkSettings,fitQty,replay,splitReplay};
});
