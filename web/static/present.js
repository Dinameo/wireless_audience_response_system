'use strict';
const $ = id => document.getElementById(id);
const examId=location.pathname.match(/^\/present\/(\d+)\/?$/)?.[1];
let data=null,index=0,review=false,terminal=false,socket=null,reconnectTimer=null,pollTimer=null,refreshPromise=null,refreshAgain=false,timerDeadline=0,controlBusy=false;
function el(tag,text,className=''){const node=document.createElement(tag);node.textContent=String(text??'');if(className)node.className=className;return node}
function notice(text){$('presentNotice').textContent=text;$('presentNotice').hidden=!text}
function connection(){const online=socket?.readyState===WebSocket.OPEN;$('liveConnection').textContent=online?'● Đồng bộ trực tiếp':'Cập nhật định kỳ';$('liveConnection').classList.toggle('offline',!online)}
function status(title,description){$('questionSlide').hidden=true;$('slideNavigation').hidden=true;$('statusSlide').hidden=false;$('statusTitle').textContent=title;$('statusDescription').textContent=description}
function renderControls(){
  const exam=data?.exam,questions=data?.questions||[],draft=exam?.status==='draft'&&questions.length>0,live=exam?.status==='open';
  const hasNext=live&&questions.some(question=>question.position>exam.current_position);
  const closed=exam?.status==='closed';
  $('teacherControls').hidden=!draft&&!live&&!closed;
  $('startExamControl').hidden=!draft;$('advanceExamControl').hidden=!hasNext;$('finishExamControl').hidden=!live;
  $('exportScoresControl').hidden=!closed;
  if(closed){$('exportScoresControl').href='/api/exams/'+examId+'/scores.xlsx';$('exportScoresControl').download='bang_diem_bai_thi_'+examId+'.xlsx'}
  for(const id of ['startExamControl','advanceExamControl','finishExamControl'])$(id).disabled=controlBusy;
  $('finishExamControl').textContent=hasNext?'Kết thúc bài thi':'Kết thúc & chấm điểm';
}
function tickSlideTimer(){const timer=$('slideTimer');if(timer.hidden)return;const ms=Math.max(0,timerDeadline-Date.now()),seconds=Math.ceil(ms/1000);timer.textContent=seconds?'Còn '+String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0'):'Hết giờ · đang chuyển câu';timer.classList.toggle('urgent',seconds<=10)}
function stopLive(){terminal=true;clearInterval(pollTimer);clearTimeout(reconnectTimer);const old=socket;socket=null;if(old)old.close()}
function unavailable(title,description,login=false){
  stopLive();data=null;controlBusy=false;renderControls();index=0;review=false;timerDeadline=0;$('slideTimer').hidden=true;$('slideOptions').replaceChildren();$('questionText').textContent='';$('examTitle').textContent='Trình chiếu bài thi';$('examMode').textContent='Không khả dụng';$('examMode').classList.remove('live');$('reviewSlides').hidden=true;$('loginLink').hidden=!login;$('liveConnection').textContent='Đã dừng đồng bộ';$('liveConnection').classList.add('offline');$('modeHint').textContent='Mở trang giảng viên để kiểm tra bài thi.';notice('');status(title,description);
}
function render(){
  if(!data)return;
  const {exam,questions,total_students}=data,live=exam.status==='open';
  renderControls();
  $('examTitle').textContent=exam.title;document.title=exam.title+' · Trình chiếu NEXUS';
  $('examMode').textContent=live?'● Đang thi':exam.status==='draft'?'Xem trước · Chưa thi':'Đã kết thúc';$('examMode').classList.toggle('live',live);
  $('reviewSlides').hidden=true;$('loginLink').hidden=true;
  if(!questions.length){status('Bài thi chưa có câu hỏi','Hãy nhập bộ câu hỏi ở tab giảng viên.');return}
  if(live){index=questions.findIndex(q=>q.position===exam.current_position);review=false;if(index<0){status('Đang chờ câu hỏi','Chưa tìm thấy câu đang mở. Màn hình sẽ tự cập nhật.');return}}
  else index=Math.max(0,Math.min(index,questions.length-1));
  if(exam.status==='closed'&&!review){status('Bài thi đã kết thúc','Cảm ơn các bạn đã tham gia! Giảng viên có thể xem điểm và kết quả ở tab quản lý.');$('reviewSlides').hidden=false;$('modeHint').textContent='Bài thi đã ngừng nhận đáp án. Xem lại slide không mở lại bài thi.';return}
  const question=questions[index];
  $('statusSlide').hidden=true;$('questionSlide').hidden=false;$('slideCounter').textContent='Câu '+question.position+' / '+questions.length;$('slidePoints').textContent=Number(question.points).toLocaleString('vi-VN',{maximumFractionDigits:2})+' điểm';$('questionText').textContent=question.text;
  const timed=live&&exam.time_limit_seconds&&exam.remaining_ms!==null;$('slideTimer').hidden=!timed;if(timed){timerDeadline=Date.now()+Number(exam.remaining_ms);tickSlideTimer()}else timerDeadline=0;
  const options=$('slideOptions');
  // Avoid rebuilding an unchanged slide for every incoming answer.
  if(options.dataset.question!==String(question.id)){
    options.replaceChildren();for(const choice of 'ABCD'){const option=el('div','','slide-option');option.append(el('span',choice,'option-letter'),el('span',question[choice.toLowerCase()],'option-text'));options.append(option)}options.dataset.question=question.id;
  }
  $('submissionProgress').hidden=!live;
  $('submissionCount').textContent=question.submitted+' / '+total_students;
  const progress=Math.min(100,Math.round(question.submitted/Math.max(1,total_students)*100));$('submissionBar').style.width=progress+'%';$('submissionBar').parentElement.setAttribute('aria-valuenow',progress);
  $('slideNavigation').hidden=live;$('previousSlide').disabled=index===0;$('nextSlide').disabled=index===questions.length-1;$('navigationCounter').textContent=(index+1)+' / '+questions.length;
  $('modeHint').textContent=live?(timed?'Hết giờ tự chuyển câu; giảng viên cũng có thể điều khiển ngay trên màn chiếu.':'Sinh viên trả lời bằng thiết bị; giảng viên chuyển câu hoặc kết thúc ngay trên màn chiếu.'):exam.status==='draft'?'Xem trước: ← / → để đổi slide. Chọn thiết bị cho từng sinh viên trước khi bắt đầu.':'Xem lại: ← / → để đổi slide. Bài thi đã kết thúc, không nhận thêm đáp án.';
}
function move(delta){if(!data||data.exam.status==='open'||(data.exam.status==='closed'&&!review))return;index=Math.max(0,Math.min(index+delta,data.questions.length-1));render()}
function confirmControl(title,text,label){
  return new Promise(resolve=>{
    const dialog=$('teacherConfirm');dialog.returnValue='';$('teacherConfirmTitle').textContent=title;$('teacherConfirmText').textContent=text;$('teacherApprove').textContent=label;
    dialog.onclose=()=>resolve(dialog.returnValue==='confirm');
    $('teacherCancel').onclick=()=>dialog.close('cancel');$('teacherApprove').onclick=()=>dialog.close('confirm');
    dialog.showModal();
  });
}
async function teacherAction(action){
  if(terminal||controlBusy||!data)return;
  const exam=data.exam,position=exam.current_position,live=exam.status==='open';
  if(action==='start'&&exam.status!=='draft')return;
  if(action!=='start'&&!live)return;
  if(action==='advance'){
    const current=data.questions.find(question=>question.position===position);
    if(!data.questions.some(question=>question.position>position))return;
    const missing=Math.max(0,Number(data.total_students)-Number(current?.submitted||0));
    if(missing&&!(await confirmControl('Chuyển câu hỏi?',`Còn ${missing} sinh viên chưa nộp câu này. Chuyển câu sẽ khóa đáp án của họ.`, 'Chuyển câu')))return;
  }
  if(action==='finish'&&!(await confirmControl('Kết thúc bài thi?', 'Bài thi sẽ ngừng nhận đáp án. Câu chưa trả lời được tính 0 điểm và kết quả sẽ được chấm ngay.', 'Kết thúc bài thi')))return;
  let selection=null;
  if(action==='start'){
    try{selection=await window.chooseExamDevices(examId)}
    catch(error){notice(error.message||'Không tải được danh sách thiết bị.');return}
    if(!selection)return;
  }
  if(!data||data.exam.status!==exam.status||data.exam.current_position!==position){notice('Trạng thái bài thi đã thay đổi. Hãy xem câu hiện tại trước khi thao tác lại.');return}
  controlBusy=true;renderControls();
  try{
    const path='/api/exams/'+examId+'/'+action+(action==='advance'?'?expected_position='+position:'');
    const response=await fetch(path,{method:'POST',credentials:'same-origin',
      headers:selection?{'Content-Type':'application/json'}:{},
      body:selection?JSON.stringify(selection):undefined,signal:AbortSignal.timeout(30000)});
    const payload=await response.json().catch(()=>({}));
    if(response.status===401){unavailable('Phiên đăng nhập đã hết hạn','Vui lòng đăng nhập lại ở tab giảng viên rồi tải lại trình chiếu.',true);return}
    if(!response.ok)throw Error(typeof payload.detail==='string'?payload.detail:'Không thể điều khiển bài thi. Vui lòng thử lại.');
    await refresh();
  }catch(error){await refresh();if(!terminal)notice(error.name==='TimeoutError'?'Máy chủ phản hồi quá lâu. Hãy kiểm tra câu hiện tại trước khi thử lại.':error.message||'Không thể điều khiển bài thi. Vui lòng thử lại.')}
  finally{controlBusy=false;renderControls()}
}
async function fetchSlide(){
  try{
    const response=await fetch('/api/exams/'+examId+'/presentation',{credentials:'same-origin',cache:'no-store',signal:AbortSignal.timeout(10000)});
    if(terminal)return;
    if(response.status===401){unavailable('Vui lòng đăng nhập','Đăng nhập giảng viên ở tab quản lý rồi tải lại màn hình trình chiếu.',true);return}
    if(response.status===404){unavailable('Bài thi không còn tồn tại','Bài thi đã bị xóa hoặc đường dẫn không đúng. Hãy chọn một bài khác ở tab giảng viên.');return}
    if(!response.ok)throw Error('Máy chủ đang bận.');
    const next=await response.json();if(terminal)return;
    if(data?.exam.status!==next.exam.status){index=0;review=false}
    data=next;notice('');connection();render();
  }catch(error){if(!terminal){notice('Mất kết nối với máy chủ. Nội dung có thể chưa cập nhật; hệ thống đang thử lại.');$('liveConnection').textContent='Mất kết nối · Đang thử lại';$('liveConnection').classList.add('offline')}}
}
async function refresh(){
  if(terminal)return;if(refreshPromise){refreshAgain=true;return refreshPromise}
  refreshPromise=(async()=>{do{refreshAgain=false;await fetchSlide()}while(refreshAgain&&!terminal)})();
  try{await refreshPromise}finally{refreshPromise=null}
}
function connectLive(){
  if(terminal)return;clearTimeout(reconnectTimer);
  const ws=new WebSocket((location.protocol==='https:'?'wss':'ws')+'://'+location.host+'/ws/teacher');socket=ws;
  ws.onmessage=event=>{if(socket!==ws||terminal)return;try{const item=JSON.parse(event.data);if(item.type==='ready'||item.type==='changed')refresh()}catch(error){notice('Không thể nhận cập nhật trực tiếp. Đang thử cập nhật định kỳ.')}};
  ws.onclose=event=>{if(socket!==ws||terminal)return;socket=null;connection();if(event.code===1008){unavailable('Phiên đăng nhập đã hết hạn','Vui lòng đăng nhập lại ở tab giảng viên rồi tải lại trình chiếu.',true);return}notice('Kết nối trực tiếp bị gián đoạn. Đang cập nhật định kỳ và kết nối lại.');reconnectTimer=setTimeout(connectLive,3000)};
  ws.onerror=()=>{if(socket===ws)notice('Không có kết nối trực tiếp. Đang thử kết nối lại.')};
}
async function fullscreen(){
  try{if(document.fullscreenElement)await document.exitFullscreen();else if(document.documentElement.requestFullscreen)await document.documentElement.requestFullscreen();else notice('Trình duyệt chưa hỗ trợ toàn màn hình. Bạn có thể dùng F11 trên máy tính.')}catch(error){notice('Không thể bật toàn màn hình. Bạn có thể dùng F11 trên máy tính.')}
}
$('previousSlide').onclick=()=>move(-1);$('nextSlide').onclick=()=>move(1);$('reviewSlides').onclick=()=>{review=true;index=0;render()};$('fullscreen').onclick=fullscreen;
$('startExamControl').onclick=()=>teacherAction('start');$('advanceExamControl').onclick=()=>teacherAction('advance');$('finishExamControl').onclick=()=>teacherAction('finish');
document.addEventListener('fullscreenchange',()=>{const active=Boolean(document.fullscreenElement);$('fullscreen').textContent=active?'Thoát toàn màn hình':'Toàn màn hình';$('fullscreen').setAttribute('aria-pressed',String(active))});
document.addEventListener('keydown',event=>{if(event.ctrlKey||event.altKey||event.metaKey||event.repeat||event.target.closest('input,select,textarea,[contenteditable="true"]'))return;if(event.key==='ArrowLeft'){event.preventDefault();move(-1)}if(event.key==='ArrowRight'){event.preventDefault();move(1)}if(event.key.toLowerCase()==='f'){event.preventDefault();fullscreen()}});
window.addEventListener('online',()=>{if(!terminal){refresh();if(!socket)connectLive()}});
window.addEventListener('pagehide',stopLive);
window.addEventListener('pageshow',event=>{if(event.persisted)location.reload()});
async function boot(){if(!examId){unavailable('Đường dẫn không hợp lệ','Hãy mở trình chiếu từ mục Bài thi.');return}await refresh();if(!terminal){connectLive();pollTimer=setInterval(refresh,10000)}}
setInterval(tickSlideTimer,250);
boot();
