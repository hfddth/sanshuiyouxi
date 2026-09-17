const $=selector=>document.querySelector(selector);
const $$=selector=>[...document.querySelectorAll(selector)];
const scenes=[
  {place:'入口',title:'风中的第一张纸条',text:'一张折起的纸条停在栏边。上面只有一句话：“顺着风，找到下一处标记。”',task:'找到纸条上的标记',action:'先观察入口附近的提示，再决定沿哪条路前进。',choices:['先看看纸条背面','沿着步道寻找标记']},
  {place:'沿岸步道',title:'第二个记号',text:'步道边出现了和纸条相似的记号。远处传来水声，线索似乎指向临水处。',task:'辨认下一个方向',action:'比较眼前的记号与纸条，选择继续寻找的方向。',choices:['记下记号的形状','前往临水处']},
  {place:'临水处',title:'故事暂时停在这里',text:'纸条上的最后一句话终于有了回应。这段示例旅程结束了，真实路线需要景区资料与现场核实。',task:'回看这段旅程',action:'整理你发现的线索，也想想下一次会如何探索。',choices:['查看我的旅程','重新体验']}
];
const state={screen:'home',style:'悬疑探索',current:0,unlocked:0,selected:[]};
let toastTimer;
function toast(message){const el=$('#toast');el.textContent=message;el.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.classList.remove('show'),2800);}
function show(screen){state.screen=screen;for(const el of $$('.screen')){const active=el.id===screen;el.hidden=!active;el.classList.toggle('active',active);}$('.bottom-nav').classList.toggle('visible',screen==='story'||screen==='journey');$$('.bottom-nav button').forEach(b=>b.classList.toggle('active',b.dataset.nav===screen));window.scrollTo({top:0,behavior:'instant'});}
function drawScene(){
  const scene=scenes[state.current];$('#scenePlace').textContent=scene.place;$('#sceneTitle').textContent=scene.title;$('#sceneText').textContent=scene.text;$('#taskTitle').textContent=scene.task;$('#taskText').textContent=scene.action;$('#sceneCounter').textContent=`第 ${String(state.current+1).padStart(2,'0')} 站`;$('#progressButton').textContent=`${String(state.current+1).padStart(2,'0')} / 03`;$('#taskProgress').textContent=`${state.current+1} / 3`;
  $('#choices').replaceChildren(...scene.choices.map((label,index)=>{const button=document.createElement('button');button.type='button';button.textContent=label;button.addEventListener('click',()=>choose(index));return button;}));
  $$('.map-node').forEach((node,i)=>{node.disabled=i>state.unlocked;node.className='map-node '+(i===state.current?'current':i<state.current?'done':i<=state.unlocked?'done':'locked');node.setAttribute('aria-label',`${scenes[i].place}，${i===state.current?'当前节点':i<=state.unlocked?'可查看':'未解锁'}`);});
  $('#mapStatus').textContent=state.current===2?'旅程已到最后一站':`${state.unlocked+1} 个地点已点亮`;
  $('#guideLine').textContent=state.current===2?'这一段故事，到这里暂时结束。':'轻触小山灵，它会回应你。';
}
function choose(index){
  const label=scenes[state.current].choices[index];
  if(state.current===2){if(index===0)showJourney();else{state.current=0;state.unlocked=0;state.selected=[];drawScene();toast('旅程重新开始');}return;}
  state.selected.push({scene:state.current,choice:label});state.current+=1;state.unlocked=Math.max(state.unlocked,state.current);drawScene();toast(index===0?'新的线索出现了':'下一处故事地点已点亮');
}
function showJourney(){const count=state.unlocked+1;$('#journeySummary').textContent=`你走过了 ${count} 处故事节点，选择了 ${state.selected.length} 次行动。当前选择的故事风格是“${state.style}”。这里展示的是界面交互样例。`;show('journey');}
$('#begin').addEventListener('click',()=>{const place=$('#place').value.trim();if(!place){toast('请输入想去的地方');$('#place').focus();return;}if(!/江心屿/.test(place)){toast('当前只提供江心屿界面样例');return;}show('setup');});
$('#place').addEventListener('keydown',event=>{if(event.key==='Enter')$('#begin').click();});
$$('.style-card').forEach(card=>card.addEventListener('click',()=>{state.style=card.dataset.style;$$('.style-card').forEach(c=>{const selected=c===card;c.classList.toggle('selected',selected);c.setAttribute('aria-checked',String(selected));});}));
$('#enterStory').addEventListener('click',()=>{state.current=0;state.unlocked=0;state.selected=[];drawScene();show('story');});
$$('[data-back]').forEach(b=>b.addEventListener('click',()=>show(b.dataset.back)));
$$('.map-node').forEach(node=>node.addEventListener('click',()=>{const next=Number(node.dataset.node);if(next<=state.unlocked){state.current=next;drawScene();toast(`已切换到${scenes[next].place}`);}}));
$('#progressButton').addEventListener('click',showJourney);
$('#returnStory').addEventListener('click',()=>show('story'));
$$('.bottom-nav button').forEach(button=>button.addEventListener('click',()=>{if(state.screen==='home'||state.screen==='setup')return;if(button.dataset.nav==='journey'){showJourney();return;}show('story');if(button.dataset.nav==='map'){$('.map-card').scrollIntoView({behavior:'smooth',block:'start'});toast('轻触已点亮的节点，查看对应故事');}}));
$('#guideTouch').addEventListener('click',()=>{const guide=$('#guideTouch');guide.classList.remove('touched');void guide.offsetWidth;guide.classList.add('touched');const lines=['我在这里，慢慢走。','这处风景，还有故事吗？','轻轻一点，我就醒啦。'];$('#guideLine').textContent=lines[Math.floor(Math.random()*lines.length)];});
$('.wordmark').addEventListener('click',event=>{event.preventDefault();show('home');});

