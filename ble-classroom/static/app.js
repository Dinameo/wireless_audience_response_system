'use strict';
const $ = id => document.getElementById(id);
const state = {teacher:null,classes:[],subjects:[],courses:[],classId:null,courseId:null,
  setupStep:1,setupSubjectId:null,setupClassId:null,setupCourseId:null,
  students:[],questions:[],exams:[],page:'overview',filter:'all',exam:null,question:null,deviceExam:null,editorStatus:null};
const pageInfo = {
  overview:['Tổng quan','Tổng quan lớp học','Sẵn sàng cho một buổi học đầy cảm hứng.'],
  management:['Lớp & môn','Thiết lập lớp học','Làm lần lượt: môn học → lớp học → sinh viên.'],
  exams:['Bài thi','Không gian bài thi','Chuẩn bị đề, điều hành buổi thi và theo dõi tiến độ.'],
  students:['Sinh viên','Kết nối với sinh viên','Danh sách lớp học và thiết bị của từng sinh viên.'],
  results:['Kết quả','Hành trình học tập','Theo dõi điểm và đáp án của từng sinh viên.'],
  imports:['Nhập dữ liệu','Tạo bài thi từ tài liệu','Nhập bộ câu hỏi Word hoặc PDF cho lớp–môn đang chọn.']
};
let authMode='login',socket=null,reconnectTimer=null,pollTimer=null,deviceTimer=null,radioTimer=null,noticeTimer=null,refreshPromise=null,refreshAgain=false;
let hostRadio=null,radioBusy=false;
function el(tag,text='',className=''){const n=document.createElement(tag);n.textContent=String(text??'');if(className)n.className=className;return n}
function icon(name){const n=document.createElementNS('http://www.w3.org/2000/svg','svg');n.setAttribute('class','icon');n.setAttribute('aria-hidden','true');const use=document.createElementNS('http://www.w3.org/2000/svg','use');use.setAttribute('href','#i-'+name);n.append(use);return n}
function action(text,handler,className='secondary'){const n=el('button',text,className);n.type='button';n.onclick=()=>handler(n);return n}
function initials(name){return name.trim().split(/\s+/).slice(-2).map(p=>p[0]).join('').toUpperCase()}
function formatScore(value){return Number(value).toLocaleString('vi-VN',{minimumFractionDigits:0,maximumFractionDigits:2})}
function empty(host,title,description,name='exam'){host.replaceChildren();const box=el('div','','empty-state');box.append(icon(name),el('h3',title),el('p',description));host.append(box)}
function message(text,error=false){clearTimeout(noticeTimer);const n=$('message');n.textContent=text;n.className='notice'+(error?' error':'');n.hidden=false;if(!error)noticeTimer=setTimeout(()=>n.hidden=true,10000)}
function authError(text){$('authError').textContent=text;$('authError').hidden=!text}
function detailMessage(detail){if(typeof detail==='string')return detail;if(Array.isArray(detail))return detail.map(x=>String(x.msg).replace(/^Value error, /,'')).join('; ');return 'Không thể xử lý yêu cầu. Vui lòng thử lại.'}
async function request(path,method='GET',body){
  const options={method,credentials:'same-origin',headers:{},signal:AbortSignal.timeout(30000)};
  if(body instanceof FormData)options.body=body;
  else if(body!==undefined){options.headers['Content-Type']='application/json';options.body=JSON.stringify(body)}
  let response;
  try{response=await fetch('/api'+path,options)}catch(e){throw Error(e.name==='TimeoutError'?'Kết nối mất quá nhiều thời gian. Vui lòng thử lại.':'Không kết nối được với máy chủ. Vui lòng kiểm tra và thử lại.')}
  const payload=await response.json().catch(()=>({detail:'Máy chủ đang bận. Vui lòng thử lại.'}));
  if(!response.ok){
    if(response.status===401&&!path.startsWith('/auth/'))showAuth('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.');
    throw Error(detailMessage(payload.detail));
  }
  return payload;
}
function setAuthMode(mode){
  authMode=mode;const registering=mode==='register';
  for(const [id,active] of [['loginTab',!registering],['registerTab',registering]]){$(id).classList.toggle('active',active);$(id).setAttribute('aria-selected',active);$(id).tabIndex=active?0:-1}
  $('registerName').hidden=!registering;$('registerConfirm').hidden=!registering;
  $('teacherName').required=registering;$('confirmPassword').required=registering;
  $('authTitle').replaceChildren(document.createTextNode(registering?'Bắt đầu hành trình mới':'Chào mừng trở lại'),el('span','.','mint'));
  $('authSubtitle').textContent=registering?'Tạo tài khoản để mở không gian giảng dạy của bạn.':'Đăng nhập để tiếp tục hành trình giảng dạy.';
  $('authSubmit').querySelector('span').textContent=registering?'Tạo tài khoản':'Đăng nhập';
  $('authSwitchLabel').textContent=registering?'Đã có tài khoản?':'Chưa có tài khoản?';
  $('switchAuth').textContent=registering?'Đăng nhập ngay':'Tạo tài khoản giảng viên';
  $('passwordHint').textContent=registering?'Mật khẩu cần ít nhất 8 ký tự.':'Phiên đăng nhập được duy trì tối đa 7 ngày.';
  $('password').autocomplete=registering?'new-password':'current-password';
  $('password').value='';$('confirmPassword').value='';$('password').type='password';
  $('togglePassword').setAttribute('aria-pressed','false');$('togglePassword').setAttribute('aria-label','Hiện mật khẩu');authError('');
}
function stopLive(){clearTimeout(reconnectTimer);clearInterval(pollTimer);clearInterval(deviceTimer);clearInterval(radioTimer);pollTimer=null;deviceTimer=null;radioTimer=null;const old=socket;socket=null;if(old)old.close()}
function showAuth(error=''){
  stopLive();state.teacher=null;state.classes=[];state.subjects=[];state.courses=[];state.classId=null;state.courseId=null;state.setupStep=1;state.setupSubjectId=null;state.setupClassId=null;state.setupCourseId=null;state.students=[];state.exams=[];state.questions=[];state.exam=null;state.question=null;state.deviceExam=null;
  if($('studentDialog').open)$('studentDialog').close();if($('examDialog').open)$('examDialog').close();if($('wifiTokenDialog').open)$('wifiTokenDialog').close();if($('radioDialog').open)$('radioDialog').close();hostRadio=null;
  $('workspace').hidden=true;$('authView').hidden=false;$('boot').hidden=true;$('message').hidden=true;
  $('password').value='';$('confirmPassword').value='';authError(error);
}
async function enterWorkspace(teacher){
  state.teacher=teacher;$('profileName').textContent=teacher.name;$('profileName').title=teacher.email;
  $('avatar').textContent=initials(teacher.name);$('welcomeName').textContent=teacher.name.split(/\s+/).at(-1);
  $('boot').hidden=true;$('authView').hidden=true;$('workspace').hidden=false;
  sessionStorage.removeItem('teacherKey');authError('');
  const page=location.hash.slice(1);go(pageInfo[page]?page:'overview',false);
  try{await refresh()}catch(e){message(e.message,true)}
  if(state.teacher){connectLive();pollTimer=setInterval(()=>refresh().catch(e=>message(e.message,true)),30000);deviceTimer=setInterval(()=>refreshDevices().catch(e=>message(e.message,true)),5000);refreshHostRadio();radioTimer=setInterval(refreshHostRadio,15000)}
}
function sidebar(open){$('sidebar').classList.toggle('is-open',open);$('sidebarBackdrop').hidden=!open;$('mobileMenu').setAttribute('aria-expanded',String(open))}
function go(page,updateHash=true){
  if(!pageInfo[page])page='overview';if(state.page!==page)$('message').hidden=true;state.page=page;
  document.querySelectorAll('[data-view]').forEach(n=>n.hidden=n.dataset.view!==page);
  document.querySelectorAll('[data-page]').forEach(n=>{const active=n.dataset.page===page;n.classList.toggle('active',active);if(active)n.setAttribute('aria-current','page');else n.removeAttribute('aria-current')});
  const info=pageInfo[page];$('breadcrumbPage').textContent=info[0];$('pageTitle').textContent=info[1];$('pageDescription').textContent=info[2];
  document.title=info[0]+' · NEXUS Classroom';
  if(updateHash&&location.hash!=='#'+page)history.pushState(null,'','#'+page);
  sidebar(false);if(page==='results')refreshResults().catch(e=>message(e.message,true));
}
function scoped(path){if(!state.courseId)throw Error('Hãy chọn lớp và môn ở thanh phía trên trước.');return path+(path.includes('?')?'&':'?')+'course_id='+state.courseId}
async function fetchContext(){
  const teacher=state.teacher;if(!teacher)return;
  const [classes,subjects]=await Promise.all([request('/classes'),request('/subjects')]);
  if(state.teacher!==teacher)return;
  state.classes=classes;state.subjects=subjects;
  const savedClass=Number(sessionStorage.getItem('nexusClass:'+teacher.id));
  if(!state.classId&&classes.some(c=>c.id===savedClass))state.classId=savedClass;
  if(!classes.some(c=>c.id===state.classId)){state.classId=classes.length===1?classes[0].id:null;state.courseId=null}
  const courses=state.classId?await request('/classes/'+state.classId+'/courses'):[];
  if(state.teacher!==teacher)return;
  state.courses=courses;
  const savedCourse=Number(sessionStorage.getItem('nexusCourse:'+teacher.id));
  if(!state.courseId&&courses.some(c=>c.id===savedCourse))state.courseId=savedCourse;
  if(!courses.some(c=>c.id===state.courseId))state.courseId=courses.length===1?courses[0].id:null;
  if(state.classId)sessionStorage.setItem('nexusClass:'+teacher.id,String(state.classId));
  if(state.courseId)sessionStorage.setItem('nexusCourse:'+teacher.id,String(state.courseId));
  renderContext();
}
function clearCourseData(){state.students=[];state.questions=[];state.exams=[];state.exam=null;state.question=null;state.deviceExam=null;renderOverview();renderStudents();renderClassRoster();renderExams();renderQuestions();renderResultOptions();if(state.page==='results')refreshResults()}
async function fetchWorkspace(){
  if(!state.teacher)return;
  const teacherId=state.teacher.id;
  await fetchContext();if(!state.teacher||state.teacher.id!==teacherId)return;
  if(!state.classId){clearCourseData();if(state.page==='overview')go('management');return}
  const classId=state.classId,courseId=state.courseId;
  const studentPath='/classes/'+classId+'/students'+(courseId?'?course_id='+courseId:'');
  const [students,questions,exams]=await Promise.all([request(studentPath),courseId?request(scoped('/questions')):[],courseId?request(scoped('/exams')):[]]);
  if(!state.teacher||state.teacher.id!==teacherId||state.classId!==classId||state.courseId!==courseId)return;
  Object.assign(state,{students,questions,exams});
  if(state.exam&&!exams.some(e=>e.id===state.exam))state.exam=null;
  if(state.deviceExam&&!exams.some(e=>e.id===state.deviceExam))state.deviceExam=null;
  renderOverview();renderStudents();renderClassRoster();renderExams();renderQuestions();renderResultOptions();
  if(state.page==='results')await refreshResults();
  if(state.deviceExam)await refreshDevices();
}
async function refresh(){
  if(refreshPromise){refreshAgain=true;return refreshPromise}
  refreshPromise=(async()=>{do{refreshAgain=false;await fetchWorkspace()}while(refreshAgain&&state.teacher)})();
  try{await refreshPromise}finally{refreshPromise=null}
}
function statusBadge(status){return el('span',status==='open'?'Đang thi':status==='closed'?'Hoàn thành':'Bản nháp','pill '+status)}
function renderContext(){
  for(const [id,items,selected,placeholder] of [['classSelect',state.classes,state.classId,'Chọn lớp'],['courseSelect',state.courses,state.courseId,'Chọn môn']]){
    const select=$(id);select.replaceChildren();const blank=el('option',placeholder);blank.value='';select.append(blank);
    for(const item of items){const option=el('option',item.name+' · '+item.code);option.value=item.id;select.append(option)}
    select.value=selected?String(selected):'';select.disabled=!items.length;
  }
  const subject=$('subjectToAdd');subject.replaceChildren();const blank=el('option','Chọn môn');blank.value='';subject.append(blank);
  for(const item of state.subjects.filter(s=>!state.courses.some(c=>c.subject_id===s.id))){const option=el('option',item.name+' · '+item.code);option.value=item.id;subject.append(option)}
  $('courseForm').querySelector('button').disabled=!state.classId||subject.options.length===1;
  $('newExam').disabled=!state.courseId;$('heroCreate').disabled=!state.courseId;
  $('courseHelp').textContent=state.classId?'Sinh viên thuộc lớp; môn mới gắn vào sẽ dùng cùng danh sách sinh viên. Chọn môn ở thanh phía trên để tạo bài thi.':'Tạo lớp sau khi có môn học, rồi gắn thêm môn nếu cần.';
  renderManagement();
}
function managementRow(item,kind){
  const row=el('div','','management-row'),copy=el('div','','row-copy');copy.append(el('strong',item.name),el('small',item.code));
  row.append(copy,action(kind==='subjects'?'Chọn môn →':'Chọn lớp →',button=>kind==='subjects'?selectSetupSubject(item):selectSetupClass(item,button),'primary'),action('Sửa',()=>editNamed(kind,item)),action('Xóa',()=>deleteNamed(kind,item),'secondary danger'));return row;
}
function showSetupStep(step){
  if(step>1&&!state.setupSubjectId){message('Hãy chọn hoặc tạo môn học trước.',true);return}
  if(step>2&&!state.setupClassId){message('Hãy chọn hoặc tạo lớp trước.',true);return}
  state.setupStep=step;renderSetup();if(state.page==='management')$('setupTitle').scrollIntoView({behavior:'smooth',block:'start'});
}
function renderSetup(){
  const subject=state.subjects.find(s=>s.id===state.setupSubjectId);
  if(!subject){state.setupSubjectId=null;state.setupClassId=null;state.setupCourseId=null;state.setupStep=1}
  const classroom=state.classes.find(c=>c.id===state.setupClassId);
  if(state.setupStep===3&&(!classroom||state.classId!==state.setupClassId)){state.setupClassId=null;state.setupCourseId=null;state.setupStep=2}
  const step=state.setupStep;
  const titles=['Bước 1 · Chọn môn học','Bước 2 · Chọn lớp học','Bước 3 · Thêm sinh viên'];
  const descriptions=['Tạo môn mới hoặc chọn môn đã có. Xong bước này sẽ chuyển sang lớp.','Tạo lớp mới hoặc chọn lớp đã có cho môn '+(subject?.name||'đang chọn')+'.','Thêm sinh viên vào '+(classroom?.name||'lớp đã chọn')+'; sau đó tạo bài thi.'];
  $('setupTitle').textContent=titles[step-1];$('setupDescription').textContent=descriptions[step-1];
  $('setupSubjectName').textContent=subject?.name||'—';$('setupClassName').textContent=classroom?.name||'lớp';
  $('classForm').querySelector('button').disabled=!subject;
  $('setupFinish').disabled=!state.setupClassId||!state.students.length;
  document.querySelectorAll('[data-setup-step]').forEach(panel=>panel.hidden=Number(panel.dataset.setupStep)!==step);
  document.querySelectorAll('[data-setup-nav]').forEach(button=>{const number=Number(button.dataset.setupNav);button.disabled=number===2?!subject:number===3?!state.setupClassId:false;button.classList.toggle('active',number===step);if(number===step)button.setAttribute('aria-current','step');else button.removeAttribute('aria-current')});
}
function selectSetupSubject(subject){state.setupSubjectId=subject.id;state.setupClassId=null;state.setupCourseId=null;showSetupStep(2)}
async function selectSetupClass(classroom,button){
  button.disabled=true;
  try{
    const courses=await request('/classes/'+classroom.id+'/courses');
    let course=courses.find(c=>c.subject_id===state.setupSubjectId);
    if(!course)course=await request('/classes/'+classroom.id+'/courses','POST',{subject_id:state.setupSubjectId});
    state.classId=classroom.id;state.courseId=course.id;state.setupClassId=classroom.id;state.setupCourseId=course.id;
    await refresh();showSetupStep(3);message('Đã chọn lớp “'+classroom.name+'”. Bây giờ thêm sinh viên vào lớp.');
  }catch(error){message(error.message,true)}finally{button.disabled=false}
}
function renderManagement(){
  $('classList').replaceChildren(...state.classes.map(c=>managementRow(c,'classes')));
  $('subjectList').replaceChildren(...state.subjects.map(s=>managementRow(s,'subjects')));
  const courseItems=state.courses.map(c=>{const row=el('div','','management-row'),copy=el('div','','row-copy');copy.append(el('strong',c.name),el('small',c.code));row.append(copy,action('Gỡ môn',()=>deleteCourse(c),'secondary danger'));return row});
  $('courseList').replaceChildren(...courseItems);
  if(!state.classes.length)empty($('classList'),'Chưa có lớp','Tạo lớp đầu tiên ở biểu mẫu bên dưới.','users');
  if(!state.subjects.length)empty($('subjectList'),'Chưa có môn','Tạo môn đầu tiên ở biểu mẫu bên dưới.','exam');
  renderSetup();
}
async function editNamed(kind,item){
  const code=window.prompt('Mã '+(kind==='classes'?'lớp':'môn')+':',item.code);if(code===null)return;
  const name=window.prompt('Tên '+(kind==='classes'?'lớp':'môn')+':',item.name);if(name===null)return;
  try{await request('/'+kind+'/'+item.id,'PATCH',{code:code.trim(),name:name.trim()});await refresh();message('Đã cập nhật '+(kind==='classes'?'lớp.':'môn.'))}catch(e){message(e.message,true)}
}
async function deleteNamed(kind,item){
  if(kind==='classes'){
    const typed=window.prompt('Xóa vĩnh viễn lớp “'+item.name+'” cùng các môn đã gắn, danh sách tham gia, câu hỏi, bài thi, đáp án và kết quả chỉ thuộc lớp này. Không thể khôi phục.\n\nHồ sơ sinh viên còn dùng ở lớp khác và môn trong thư viện vẫn được giữ.\n\nGõ mã lớp '+item.code+' để xác nhận:');
    if(typed===null)return;
    if(typed.trim()!==item.code){message('Mã lớp không khớp. Chưa xóa dữ liệu.',true);return}
  }else if(!window.confirm('Xóa môn “'+item.name+'”? Chỉ xóa được khi môn chưa gắn với lớp nào.'))return;
  try{await request('/'+kind+'/'+item.id,'DELETE');if(kind==='classes'){if(state.classId===item.id){state.classId=null;state.courseId=null;sessionStorage.removeItem('nexusClass:'+state.teacher.id);sessionStorage.removeItem('nexusCourse:'+state.teacher.id)}if(state.setupClassId===item.id){state.setupClassId=null;state.setupCourseId=null;state.setupStep=2}}else if(state.setupSubjectId===item.id){state.setupSubjectId=null;state.setupClassId=null;state.setupCourseId=null;state.setupStep=1}await refresh();message(kind==='classes'?'Đã xóa vĩnh viễn lớp và dữ liệu chỉ thuộc lớp đó.':'Đã xóa môn.')}catch(e){message(e.message,true)}
}
async function deleteCourse(course){
  if(!window.confirm('Gỡ môn “'+course.name+'” khỏi lớp? Chỉ gỡ được môn chưa có bài thi hoặc câu hỏi. Sinh viên vẫn ở trong lớp.'))return;
  try{await request('/courses/'+course.id,'DELETE');if(state.courseId===course.id){state.courseId=null;sessionStorage.removeItem('nexusCourse:'+state.teacher.id)}await refresh();message('Đã gỡ môn.')}catch(e){message(e.message,true)}
}
function renderOverview(){
  $('statExams').textContent=state.exams.length;$('navExamCount').textContent=state.exams.length;
  $('statStudents').textContent=state.students.length;
  $('statDrafts').textContent=state.exams.filter(e=>e.status==='draft').length+' bài đang chuẩn bị';
  $('statActive').textContent=state.exams.filter(e=>e.status==='open').length;
  $('statCompleted').textContent=state.exams.filter(e=>e.status==='closed').length;
  const host=$('recentExams');host.replaceChildren();
  if(!state.exams.length){empty(host,'Chưa có bài thi','Nhập tài liệu để chuẩn bị bài thi đầu tiên.');return}
  for(const exam of state.exams.slice(0,4)){
    const row=el('div','','recent-row'),info=el('div','','recent-info'),mark=el('span','','stat-icon mint');mark.append(icon('exam'));
    const copy=el('div');copy.append(action(exam.title,()=>{go('exams');$('examSearch').value=exam.title;renderExams()},'recent-title'),el('small',exam.question_count+' câu hỏi · Bài thi #'+exam.id));
    info.append(mark,copy);row.append(info,statusBadge(exam.status));host.append(row);
  }
}
function renderStudents(){
  $('studentCount').textContent=state.students.length;
  const query=$('studentSearch').value.trim().toLocaleLowerCase('vi');
  const students=state.students.filter(s=>[s.name,s.mssv,s.device_id].some(v=>String(v).toLocaleLowerCase('vi').includes(query)));
  if(!students.length){empty($('students'),query?'Không tìm thấy sinh viên':'Danh sách lớp đang trống',query?'Thử tìm theo tên, MSSV hoặc mã thiết bị khác.':'Nhập file Excel để chuẩn bị danh sách lớp.','users');return}
  const guide=el('p','Chọn “Thiết lập” để chọn nRF52840 hoặc ESP32, rồi nhập mã bo. Mã bo được xác nhận lại khi bắt đầu từng bài thi.','student-directory-guide');
  const table=el('table'),head=el('thead'),tr=el('tr');for(const title of ['Sinh viên','Thiết bị dự định','Sẵn sàng','Điểm TB (/10)','Thao tác'])tr.append(el('th',title));head.append(tr);table.append(head);
  const body=el('tbody');
  for(const s of students){
    const protocol=s.preferred_protocol==='WIFI'?'WIFI':'BLE';
    const row=el('tr'),identity=el('td'),name=el('div','','student-name'),copy=el('div');
    copy.append(el('strong',s.name),el('small',s.mssv));name.append(el('span',initials(s.name),'avatar'),copy);identity.append(name);
    const device=el('td'),deviceInfo=el('div','','student-device-info');
    deviceInfo.append(el('strong',protocol==='WIFI'?'ESP32 · Wi-Fi':'nRF52840 · BLE','protocol-pill '+(protocol==='WIFI'?'wifi':'ble')),
      el('span',s.device_id||'Chưa chọn mã bo',s.device_id?'device-tag':'muted'));device.append(deviceInfo);
    const status=el('td');
    if(protocol==='WIFI')status.append(el('span',s.wifi_enabled?'Đã cấp mã Wi-Fi':'Cần kích hoạt Wi-Fi','device-state '+(s.wifi_enabled?'connected':'weak')));
    else status.append(el('span',s.device_id?(s.ble_online?'BLE đang kết nối':'Chưa thấy tín hiệu BLE'):'Chưa có mã bo','device-state '+(s.ble_online?'connected':'unknown')));
    const controls=el('td'),actions=el('div','','student-actions');
    actions.append(action('Thiết lập',()=>openStudentEditor(s),'secondary'));
    if(protocol==='WIFI'&&!s.wifi_enabled){const activate=action('Tạo token',b=>issueWifiToken(s,b),'primary');activate.disabled=!state.courseId||!s.device_id;activate.title=s.device_id?'Tạo token để dán vào firmware ESP32.':'Lưu mã thiết bị ESP32 trước.';actions.append(activate)}
    const more=el('details','','student-more'),summary=el('summary','Tùy chọn');more.append(summary);
    if(protocol==='WIFI'&&s.wifi_enabled){more.append(action('Cấp lại token',b=>issueWifiToken(s,b)));more.append(action('Thu hồi Wi-Fi',b=>revokeWifiToken(s,b),'secondary danger'))}
    more.append(action('Bỏ khỏi lớp',()=>removeStudent(s),'secondary danger'));actions.append(more);controls.append(actions);
    row.append(identity,device,status,el('td',s.score===null?'—':formatScore(s.score),'score'),controls);body.append(row);
  }
  table.append(body);const wrap=el('div','','table');wrap.append(table);$('students').replaceChildren(guide,wrap);
}
function renderClassRoster(){
  $('classStudentCount').textContent=state.classId?state.students.length+' sinh viên':'Chưa chọn lớp';
  $('setupFinish').disabled=!state.setupClassId||!state.students.length;
  const host=$('classRosterPreview');host.replaceChildren();
  if(!state.classId){host.append(el('p','Hãy tạo hoặc chọn lớp trước khi thêm sinh viên.','field-hint'));return}
  if(!state.students.length){host.append(el('p','Lớp chưa có sinh viên. Thêm thủ công ở đây hoặc nhập Excel.','field-hint'));return}
  for(const student of state.students.slice(0,5)){const row=el('div','','management-row');row.append(el('strong',student.name),el('small',student.mssv+' · '+(student.device_id||'Chọn thiết bị khi thi')));host.append(row)}
  if(state.students.length>5)host.append(el('p','Còn '+(state.students.length-5)+' sinh viên khác. Xem toàn bộ ở mục Sinh viên.','field-hint'));
}
async function perform(path,button,success='Đã cập nhật bài thi.',method='POST',onSuccess=null){
  if(button)button.disabled=true;
  try{await request(path,method);if(onSuccess)onSuccess();await refresh();message(success)}catch(e){message(e.message,true)}finally{if(button)button.disabled=false}
}
function showExamResults(id){state.exam=id;state.question=null;go('results');$('resultExamSelect').value=String(id)}
function updateDeviceHints(prefix){
  const protocol=$(prefix==='edit'?'editProtocol':'studentProtocol').value;
  const device=$(prefix==='edit'?'editDevice':'device');
  const hint=$(prefix==='edit'?'editDeviceHint':'studentDeviceHint');
  device.placeholder=protocol==='WIFI'?'VD: ESP32-01':'VD: NRF-...';
  hint.textContent=protocol==='WIFI'?'ESP32: nhập mã bo (không phải token). Lưu xong chọn “Tạo token” để lấy mã bí mật cho firmware.':'nRF: dùng mã bo gateway nhận qua Bluetooth. Không cần token Wi-Fi.';
  if(prefix==='edit'){
    const wifiHint=$('editWifiHint');
    wifiHint.hidden=protocol!=='WIFI';
    wifiHint.textContent=$('studentDialog').dataset.wifiEnabled==='true'?'Token đã cấp cho mã bo đang lưu. Đổi mã bo sẽ cần tạo token cho bo mới.':'Sau khi lưu mã bo, trở về danh sách và bấm “Tạo token”.';
  }
}
function openStudentEditor(student){$('editStudentId').value=student.id;$('editStudentRevision').value=student.revision;$('editMssv').value=student.mssv;$('editName').value=student.name;$('editProtocol').value=student.preferred_protocol==='WIFI'?'WIFI':'BLE';$('editDevice').value=student.device_id;$('studentDialog').dataset.wifiEnabled=String(Boolean(student.wifi_enabled));updateDeviceHints('edit');$('studentDialog').showModal()}
async function issueWifiToken(student,button){
  if(student.wifi_enabled&&!window.confirm('Cấp lại token cho thiết bị “'+student.device_id+'”? Token cũ trên bo sẽ ngừng hoạt động ngay, kể cả khi bo được dùng ở lớp khác.'))return;
  button.disabled=true;try{const result=await request(scoped('/students/'+student.id+'/wifi-token'),'POST');$('wifiTokenOwner').textContent=student.name+' · '+student.mssv+' · '+result.device_id;$('wifiTokenValue').value=result.token;$('wifiTokenDialog').showModal();$('wifiTokenValue').select();await refresh()}catch(e){message(e.message,true)}finally{button.disabled=false}
}
async function revokeWifiToken(student,button){
  if(!window.confirm('Thu hồi mã ESP32 của thiết bị “'+student.device_id+'”? Board này sẽ không gửi được tín hiệu hay đáp án Wi-Fi nữa ở mọi lớp.'))return;
  button.disabled=true;try{await request(scoped('/students/'+student.id+'/wifi-token'),'DELETE');await refresh();message('Đã thu hồi mã ESP32. Thiết bị Wi-Fi đã ngừng được phép nộp bài.')}catch(e){message(e.message,true)}finally{button.disabled=false}
}
async function removeStudent(student){
  if(!window.confirm('Bỏ “'+student.name+'” khỏi lớp đang chọn và các môn của lớp? Kết quả bài thi cũ vẫn được giữ.'))return;
  try{await request('/classes/'+state.classId+'/students/'+student.id,'DELETE');await refresh();message('Đã bỏ sinh viên khỏi lớp. Kết quả thi cũ được giữ.')}catch(e){message(e.message,true)}
}
function finishExam(exam,button){
  if(!window.confirm('Kết thúc bài thi “'+exam.title+'” ngay bây giờ?\n\nGiữ nguyên đáp án đã nộp. Các câu chưa trả lời được tính 0 điểm. Sinh viên sẽ không thể nộp thêm.'))return;
  return perform('/exams/'+exam.id+'/finish',button,'Đã kết thúc bài thi. Kết quả và điểm đã được cập nhật.','POST',()=>showExamResults(exam.id));
}
async function retakeExam(exam,button){
  button.disabled=true;
  try{const result=await request('/exams/'+exam.id+'/retake','POST');state.filter='all';$('examSearch').value='';document.querySelectorAll('[data-filter]').forEach(n=>n.classList.toggle('active',n.dataset.filter==='all'));await refresh();go('exams');message('Đã tạo “'+result.title+'” (#'+result.exam_id+'). Hãy kiểm tra đề rồi bấm Bắt đầu & trình chiếu. Điểm cũ vẫn được giữ.')}catch(e){message(e.message,true)}finally{button.disabled=false}
}
async function startExam(exam,button){
  button.disabled=true;
  // Open the preview during the click gesture; it becomes live after check-in.
  const slide=window.open('/present/'+exam.id,'_blank');
  try{
    const selection=await window.chooseExamDevices(exam.id);
    if(!selection){if(slide&&!slide.closed)slide.close();return}
    await request('/exams/'+exam.id+'/start','POST',selection);
  }catch(error){if(slide&&!slide.closed)slide.close();message(error.message,true);return}
  finally{button.disabled=false}
  await refresh().catch(error=>message(error.message,true));
  if(slide&&!slide.closed){
    message('Đã chốt thiết bị và bắt đầu bài thi. Sinh viên chọn đáp án trên thiết bị.');
    return;
  }
  window.location.assign('/present/'+exam.id);
}
function deleteExam(exam,button){
  const warning=exam.status==='open'?'Bài thi đang diễn ra sẽ bị dừng.\n\n':'';
  if(!window.confirm('Xóa bài thi “'+exam.title+'” (#'+exam.id+')?\n\n'+warning+'Toàn bộ câu hỏi và kết quả của bài thi này sẽ bị xóa vĩnh viễn, không thể khôi phục. Danh sách sinh viên được giữ nguyên.'))return;
  return perform('/exams/'+exam.id,button,'Đã xóa bài thi cùng câu hỏi và kết quả. Danh sách sinh viên được giữ nguyên.','DELETE');
}
function questionEditorCard(question={}){
  const card=el('div','','edit-question'),top=el('div','','edit-question-top');top.append(el('h3','Câu hỏi'),action('Bỏ câu',()=>{if($('editQuestions').children.length<2){message('Bài thi cần ít nhất một câu hỏi.',true);return}card.remove();renumberEditor()},'secondary danger'));card.append(top);
  const textLabel=el('label','Nội dung câu hỏi'),textInput=el('textarea',question.text||'');textInput.dataset.field='text';textInput.required=true;textInput.maxLength=1000;textLabel.append(textInput);card.append(textLabel);
  const grid=el('div','','edit-question-grid');
  for(const key of 'abcd'){
    const label=el('label','Đáp án '+key.toUpperCase()),input=el('input');input.type='text';input.value=question[key]||'';input.dataset.field=key;input.required=true;input.maxLength=500;label.append(input);grid.append(label);
  }
  const correctLabel=el('label','Đáp án đúng'),correct=el('select');correct.dataset.field='correct_choice';for(const choice of 'ABCD'){const option=el('option',choice);option.value=choice;correct.append(option)}correct.value=question.correct_choice||'A';correctLabel.append(correct);grid.append(correctLabel);
  card.append(grid);return card;
}
function renumberEditor(){$('editQuestions').querySelectorAll('.edit-question h3').forEach((n,i)=>n.textContent='Câu '+(i+1))}
async function openExamEditor(exam){
  try{
    const data=await request('/exams/'+exam.id+'/editor');state.editorStatus=data.exam.status;
    $('editExamId').value=exam.id;$('editExamRevision').value=data.exam.revision;$('editExamTitle').value=data.exam.title;$('editTimeLimit').value=data.exam.time_limit_seconds??'';
    const draft=data.exam.status==='draft';$('examDialogTitle').textContent=draft?'Chỉnh sửa đề thi':'Đổi tên bài thi';
    $('examEditHint').textContent=draft?'Chỉ đề nháp mới sửa được câu hỏi và đáp án. Tổng 10 điểm được chia lại đều theo số câu mỗi lần lưu.':'Bài đã thi chỉ được đổi tên; nội dung và đáp án bị khóa để bảo vệ kết quả.';
    $('editQuestions').replaceChildren(...data.questions.map(q=>questionEditorCard(q)));
    $('editTimerControls').hidden=!draft;$('editQuestions').hidden=!draft;$('addExamQuestion').hidden=!draft;renumberEditor();$('examDialog').showModal();
  }catch(e){message(e.message,true)}
}
function deviceLabel(value){return ({connected:'Đang kết nối',disconnected:'Đã ngắt',stale:'Mất tín hiệu',unknown:'Chưa có tín hiệu',simulated:'Mô phỏng',stable:'Ổn định',observing:'Đang xác nhận',weak:'Tín hiệu yếu'})[value]||'Chưa rõ'}
function clockText(ms){const seconds=Math.ceil(Math.max(0,ms)/1000);return String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0')}
function tickCountdowns(){for(const timer of document.querySelectorAll('.exam-timer[data-deadline]')){const remaining=Math.max(0,Number(timer.dataset.deadline)-Date.now());timer.textContent=remaining>0?'Còn '+clockText(remaining):'Hết giờ · đang chuyển câu';timer.classList.toggle('urgent',remaining<=10000)}}
async function refreshDevices(){
  const id=state.deviceExam;if(!id||!state.teacher)return;
  const host=document.querySelector('[data-device-exam="'+id+'"]');if(!host)return;
  const data=await request('/exams/'+id+'/devices');if(state.deviceExam!==id||!host.isConnected)return;
  host.replaceChildren(el('h4','Thiết bị tham gia bài thi'),el('p','Trạng thái lấy từ gateway BLE hoặc trực tiếp từ ESP32 Wi-Fi; nộp đáp án mô phỏng không đồng nghĩa với thiết bị đã kết nối. Mất heartbeat quá 15 giây sẽ hiện “Mất tín hiệu”. Trên điện thoại, vuốt bảng sang ngang để xem đủ thông tin.','field-hint'));
  const summary=el('div','','device-summary');summary.append(el('span','BLE/USB/Wi-Fi đang kết nối: '+data.connected+'/'+data.total),el('span','Mô phỏng: '+data.simulated));host.append(summary);
  const table=el('table'),head=el('thead'),row=el('tr');for(const text of ['Sinh viên','MSSV','Thiết bị','Giao thức','Nguồn tín hiệu','Kết nối','Ổn định','RSSI','Tín hiệu gần nhất','Câu hiện tại'])row.append(el('th',text));head.append(row);table.append(head);
  const body=el('tbody');for(const d of data.devices){const tr=el('tr');for(const value of [d.name,d.mssv,d.device_id,d.protocol||d.expected_protocol+' (dự kiến)',d.gateway_id||'—'])tr.append(el('td',value));
    const status=el('td');status.append(el('span',deviceLabel(d.status),'device-state '+d.status));tr.append(status);
    const quality=el('td');quality.append(el('span',deviceLabel(d.stability),'device-state '+d.stability));tr.append(quality);
    for(const value of [d.rssi===null?'—':d.rssi+' dBm',d.age_seconds===null?'Chưa ghi nhận':d.age_seconds+' giây trước',data.exam.status==='open'?(d.submitted_current?'Đã nộp':'Chưa nộp'):'—'])tr.append(el('td',value));body.append(tr)}
  table.append(body);const wrap=el('div','','table');wrap.append(table);host.append(wrap);
}
function renderExams(){
  const host=$('exams');host.replaceChildren();
  const query=$('examSearch').value.toLocaleLowerCase('vi').trim();
  const exams=state.exams.filter(e=>(state.filter==='all'||e.status===state.filter)&&e.title.toLocaleLowerCase('vi').includes(query));
  if(!exams.length){empty(host,'Chưa có bài thi phù hợp',state.exams.length?'Đổi bộ lọc hoặc từ khóa tìm kiếm.':'Tạo bài thi từ một bộ câu hỏi Word hoặc PDF.');return}
  for(const exam of exams){
    const box=el('article','','exam-card'),top=el('div','','exam-card-top'),mark=el('span','','stat-icon mint');mark.append(icon('exam'));top.append(mark,statusBadge(exam.status));
    box.append(top,el('h3',exam.title),el('p',exam.question_count+' câu hỏi · Bài thi #'+exam.id,'exam-meta'));
    if(exam.time_limit_seconds){const timer=el('div',exam.status==='open'?'':'Hẹn giờ: '+exam.time_limit_seconds+' giây/câu','exam-timer');if(exam.status==='open'&&exam.remaining_ms!==null)timer.dataset.deadline=String(Date.now()+Number(exam.remaining_ms));box.append(timer)}
    if(exam.status==='open'){
      box.append(el('p','Câu '+exam.current_position+'/'+exam.question_count+' · '+Number(exam.current_submitted||0)+'/'+exam.participant_count+' sinh viên đã nộp','exam-meta'));
      const track=el('div','','progress-track'),bar=el('span');bar.style.width=Math.min(100,(Number(exam.current_submitted||0)/Math.max(1,exam.participant_count))*100)+'%';track.append(bar);box.append(track,el('div',exam.current_question,'exam-question'));
      const options=el('div','','exam-options');for(const choice of 'ABCD')options.append(el('div',choice+'. '+exam['current_'+choice.toLowerCase()]));box.append(options);
    }
    const actions=el('div','','actions');
    if(exam.status==='draft')actions.append(action('Chọn thiết bị & bắt đầu',b=>startExam(exam,b),'primary'));
    if(exam.status==='closed')actions.append(action('Thi lại',b=>retakeExam(exam,b),'primary'));
    if(exam.status==='open'){
      const last=Number(exam.current_position)>=Number(exam.question_count);
      if(!last)actions.append(action('Chuyển câu tiếp theo',b=>perform('/exams/'+exam.id+'/advance?expected_position='+exam.current_position,b)));
      actions.append(action('Kết thúc bài thi',b=>finishExam(exam,b),'secondary danger'));
    }
    const present=el('a','Trình chiếu bài thi','secondary');present.href='/present/'+exam.id;present.target='_blank';present.rel='noopener';present.title='Mở trình chiếu trong tab mới';
    actions.append(action(exam.status==='draft'?'Chỉnh đề thi':'Đổi tên',()=>openExamEditor(exam)),action(state.deviceExam===exam.id?'Ẩn thiết bị':'Xem thiết bị',()=>{state.deviceExam=state.deviceExam===exam.id?null:exam.id;renderExams();refreshDevices().catch(e=>message(e.message,true))}),present,action('Xem kết quả',()=>showExamResults(exam.id)));
    if(exam.status==='closed'){const exportLink=el('a','↓ Xuất điểm Excel','secondary');exportLink.href='/api/exams/'+exam.id+'/scores.xlsx';exportLink.download='bang_diem_bai_thi_'+exam.id+'.xlsx';actions.append(exportLink)}
    actions.append(action('Xóa bài thi',b=>deleteExam(exam,b),'secondary danger'));
    box.append(actions);if(state.deviceExam===exam.id){box.classList.add('expanded');const devices=el('div','Đang tải trạng thái thiết bị…','device-panel');devices.dataset.deviceExam=exam.id;box.append(devices)}host.append(box);
  }
  tickCountdowns();
}
function renderQuestions(){
  const host=$('questions');host.replaceChildren();
  if(!state.questions.length){empty(host,'Chưa có câu hỏi riêng lẻ','Các câu hỏi trong bài thi nằm ở danh sách phía trên.');return}
  for(const q of state.questions){const box=el('article','','exam-card');box.append(el('h3','#'+q.id+' · '+q.text),statusBadge(q.status));const actions=el('div','','actions');actions.append(action('Xem kết quả',()=>{state.question=q.id;state.exam=null;$('resultExamSelect').value='';go('results')}));
    if(q.status==='draft')actions.append(action('Mở nhận đáp án',b=>perform('/questions/'+q.id+'/open',b),'primary'));
    if(q.status==='open')actions.append(action('Đóng câu hỏi',b=>perform('/questions/'+q.id+'/close',b),'secondary danger'));
    actions.append(action('Xóa câu hỏi',b=>{if(!window.confirm('Xóa vĩnh viễn câu hỏi #'+q.id+' cùng đáp án và kết quả của câu này? Không thể khôi phục.'))return;return perform('/questions/'+q.id,b,'Đã xóa vĩnh viễn câu hỏi và kết quả.','DELETE')},'secondary danger'));
    box.append(actions);host.append(box)}
}
function renderResultOptions(){
  const select=$('resultExamSelect');select.replaceChildren(el('option','Chọn bài thi'));select.firstChild.value='';
  for(const exam of state.exams){const option=el('option',exam.title);option.value=exam.id;select.append(option)}
  select.value=state.exam?String(state.exam):'';
}
async function refreshResults(){
  const exam=state.exam,question=state.question;
  if(exam){const data=await request('/exams/'+exam+'/summary');if(state.exam===exam)renderExamSummary(data)}
  else if(question){const data=await request('/questions/'+question+'/results');if(state.question===question)renderQuestionResults(data)}
  else{$('resultTitle').textContent='Kết quả bài thi';empty($('results'),'Nhìn lại hành trình học tập','Chọn một bài thi để xem điểm và đáp án của từng sinh viên.','chart')}
}
function renderExamSummary(r){
  $('resultTitle').textContent=r.exam.title;const host=$('results');host.className='';host.replaceChildren();
  const legend=el('div','','result-legend');legend.append(el('strong','Điểm tối đa: '+formatScore(r.max_score)),el('span','✓ Đúng','answer-correct'),el('span','✗ Sai','answer-wrong'),el('span','— Chưa nộp','answer-missing'));host.append(legend);
  if(r.exam.status==='closed'){
    const exportLink=el('a','↓ Tải bảng điểm Excel','secondary score-export');
    exportLink.href='/api/exams/'+r.exam.id+'/scores.xlsx';
    exportLink.download='bang_diem_bai_thi_'+r.exam.id+'.xlsx';
    host.append(exportLink,scoreChart(r.students,r.max_score));
  }
  if(r.exam.status!=='closed')host.append(el('p','Bài thi chưa kết thúc. Điểm dưới đây là kết quả tạm thời.','field-hint'));
  const table=el('table'),head=el('thead'),tr=el('tr');for(const h of ['MSSV','Họ tên','Thiết bị đã dùng',...r.questions.map(q=>'Câu '+q.position),'Tổng điểm'])tr.append(el('th',h));head.append(tr);table.append(head);const body=el('tbody');
  for(const student of r.students){const row=el('tr');row.append(el('td',student.mssv),el('td',student.name),el('td',student.device_id||'—'));
    for(const answer of student.answers){const missing=answer.choice===null;const cell=el('td',missing?'—':answer.choice+(answer.correct?' ✓':' ✗'),missing?'answer-missing':answer.correct?'answer-correct':'answer-wrong');cell.title='Đáp án đúng: '+answer.correct_choice;row.append(cell)}
    row.append(el('td',formatScore(student.score)+'/'+formatScore(r.max_score),'score'));body.append(row)}
  table.append(body);const wrap=el('div','','table');wrap.append(table);host.append(wrap);
}
function scoreChart(students,maxScore){
  const chart=el('section','','score-chart');chart.append(el('h3','Biểu đồ điểm cả lớp'));
  if(!students.length){chart.append(el('p','Chưa có sinh viên tham gia.','field-hint'));return chart}
  const scores=students.map(s=>Number(s.score)||0),average=scores.reduce((sum,score)=>sum+score,0)/scores.length;
  const stats=el('div','','score-chart-stats');stats.append(el('span','Số sinh viên: '+students.length),el('span','Trung bình: '+formatScore(average)+'/'+formatScore(maxScore)),el('span','Cao nhất: '+formatScore(Math.max(...scores))),el('span','Từ 5 điểm: '+scores.filter(score=>score>=5).length));chart.append(stats);
  const tabs=el('div','','score-chart-tabs'),plot=el('div','','score-chart-content');chart.append(tabs,plot);
  const modes=[['bar','Biểu đồ cột'],['line','Biểu đồ đường'],['distribution','Phân bố điểm']];
  function draw(mode){
    for(const button of tabs.children){const active=button.dataset.mode===mode;button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active))}
    plot.replaceChildren();
    if(mode==='distribution'){
      const bins=[0,0,0,0,0];for(const score of scores)bins[Math.min(4,Math.floor(Math.max(0,score)/2))]++;
      const bars=el('div','','score-chart-bars');bars.setAttribute('role','img');bars.setAttribute('aria-label','Phân bố điểm: '+bins.map((count,i)=>['0–<2','2–<4','4–<6','6–<8','8–10'][i]+' điểm: '+count+' sinh viên').join('; '));
      const peak=Math.max(1,...bins);
      bins.forEach((count,i)=>{const group=el('div','','score-chart-group'),area=el('div','','score-chart-plot'),bar=el('div','','score-chart-bar');bar.style.height=(count?Math.max(8,count/peak*100):2)+'%';area.append(bar);group.append(el('strong',count),area,el('span',['0–<2','2–<4','4–<6','6–<8','8–10'][i]));bars.append(group)});
      plot.append(bars);return;
    }
    const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');
    const width=Math.max(620,students.length*64+70),height=310,left=42,top=18,bottom=246,usable=width-left-20;
    svg.setAttribute('viewBox',`0 0 ${width} ${height}`);svg.setAttribute('width',width);svg.setAttribute('height',height);
    svg.setAttribute('role','img');svg.setAttribute('aria-label',(mode==='bar'?'Biểu đồ cột':'Biểu đồ đường')+' điểm của '+students.length+' sinh viên, thang '+formatScore(maxScore));
    const node=(tag,attrs={},label='')=>{const item=document.createElementNS(ns,tag);for(const [key,value] of Object.entries(attrs))item.setAttribute(key,String(value));if(label)item.textContent=label;svg.append(item);return item};
    for(let mark=0;mark<=maxScore;mark+=2){const y=bottom-(mark/maxScore)*(bottom-top);node('line',{x1:left,y1:y,x2:width-20,y2:y,class:'score-grid-line'});node('text',{x:left-9,y:y+4,'text-anchor':'end',class:'score-axis-label'},formatScore(mark))}
    const gap=usable/students.length,points=[];
    students.forEach((student,i)=>{
      const x=left+gap*(i+0.5),y=bottom-(scores[i]/maxScore)*(bottom-top),tip=student.mssv+' · '+student.name+': '+formatScore(scores[i])+'/'+formatScore(maxScore);
      if(mode==='bar'){const rect=node('rect',{x:x-Math.min(16,gap*.3),y,width:Math.min(32,gap*.6),height:Math.max(0,bottom-y),rx:5,class:'score-svg-bar'});const title=document.createElementNS(ns,'title');title.textContent=tip;rect.append(title)}
      points.push(x+','+y);
      node('text',{x,y:bottom+18,'text-anchor':'middle',class:'score-axis-label'},student.mssv);
    });
    if(mode==='line'){
      node('polyline',{points:points.join(' '),fill:'none',class:'score-svg-line'});
      students.forEach((student,i)=>{const [x,y]=points[i].split(',');const dot=node('circle',{cx:x,cy:y,r:5,class:'score-svg-dot'});const title=document.createElementNS(ns,'title');title.textContent=student.mssv+' · '+student.name+': '+formatScore(scores[i])+'/'+formatScore(maxScore);dot.append(title)})
    }
    plot.append(svg);
  }
  for(const [mode,label] of modes){const button=action(label,()=>draw(mode),'score-chart-tab');button.dataset.mode=mode;tabs.append(button)}
  draw('bar');return chart;
}
function renderQuestionResults(r){
  $('resultTitle').textContent='Câu #'+r.question.id+' · '+r.question.text;const host=$('results');host.className='';host.replaceChildren(el('p',r.submitted+'/'+r.total+' sinh viên đã nộp. '+(r.question.status==='closed'?'Đáp án đúng: '+r.question.correct_choice:'Đáp án đúng được ẩn đến khi đóng câu hỏi.'),'result-legend'));
  const counts=el('div','','counts');for(const c of 'ABCD'){const box=el('div',c,'count');box.append(el('strong',r.counts[c]));counts.append(box)}host.append(counts);
  const table=el('table'),head=el('tr');for(const h of ['MSSV','Họ tên','Thiết bị','Lựa chọn','Điểm'])head.append(el('th',h));table.append(head);
  for(const s of r.students){const row=el('tr');for(const value of [s.mssv,s.name,s.device_id,s.choice??'Chưa nộp',formatScore(s.awarded_points)])row.append(el('td',value));table.append(row)}
  const wrap=el('div','','table');wrap.append(table);host.append(wrap);
}
function renderHostRadio(data){
  hostRadio=data;
  const service=Boolean(data?.service_available);
  const wifi=data?.wifi,ble=data?.ble;
  $('radioOpen').textContent=service?`Wi‑Fi: ${wifi?.connected?'đã nối':wifi?.enabled?'đang bật':'tắt'} · BLE: ${ble?.enabled?'bật':'tắt'}`:'Wi‑Fi / BLE: chưa kiểm tra được';
  $('radioOpen').classList.toggle('radio-unavailable',!service);
  $('radioMessage').textContent=service?'Trạng thái laptop được cập nhật tự động mỗi 15 giây.':data?.message||'Chưa kết nối được với dịch vụ radio trên laptop.';
  for(const [radio,info,stateId,detailId,buttonId] of [
    ['wifi',wifi,'wifiRadioState','wifiRadioDetail','wifiRadioToggle'],
    ['ble',ble,'bleRadioState','bleRadioDetail','bleRadioToggle']]){
    const label=radio==='wifi'?'Wi‑Fi':'BLE',button=$(buttonId);
    $(stateId).textContent=!service?'Chưa đọc được':info?.error?'Không đọc được':!info?.available?'Laptop không có adapter':info.enabled?'Đang bật':'Đang tắt';
    $(detailId).textContent=info?.error||(!service?'Cần chạy dịch vụ radio trên laptop.':radio==='wifi'&&info?.connected?'Đã kết nối mạng '+info.connection:radio==='wifi'&&info?.enabled?'Đã bật nhưng chưa vào mạng; ESP32 cần cùng mạng LAN.':radio==='ble'&&info?.enabled?'Bluetooth đã cấp nguồn; xem kết nối bo nRF ở mục Sinh viên.':'');
    button.textContent=info?.enabled?'Tắt '+label:'Bật '+label;
    button.disabled=radioBusy||!service||!info?.available||info.enabled===null||Boolean(info.error);
    button.setAttribute('aria-pressed',String(Boolean(info?.enabled)));
  }
}
async function refreshHostRadio(){
  if(!state.teacher||radioBusy)return;
  const teacher=state.teacher;
  try{const data=await request('/host-radio');if(state.teacher===teacher)renderHostRadio(data)}
  catch(error){if(state.teacher===teacher)renderHostRadio({service_available:false,message:error.message})}
}
async function setHostRadio(radio){
  if(radioBusy||!hostRadio?.service_available)return;
  const info=hostRadio[radio];if(!info?.available||info.enabled===null)return;
  const enabled=!info.enabled;
  if(!enabled){
    const warning=radio==='wifi'?'Tắt Wi‑Fi của laptop sẽ ngắt ESP32, gateway từ xa và có thể mất trang web trên máy khác. Chỉ tắt nếu bạn có thể bật lại tại laptop hoặc qua Ethernet.':'Tắt Bluetooth của laptop sẽ ngắt các bo nRF đang kết nối với gateway.';
    if(!window.confirm(warning+'\n\nBạn chắc chắn muốn tắt '+(radio==='wifi'?'Wi‑Fi':'BLE')+'?'))return;
  }
  radioBusy=true;renderHostRadio(hostRadio);
  let errorText='';
  try{const data=await request('/host-radio/'+radio,'POST',{enabled});renderHostRadio(data);if(data[radio]?.enabled!==enabled)throw Error('Laptop chưa chuyển được radio sang trạng thái yêu cầu. Hãy xem lại trạng thái và thử lại.');message((radio==='wifi'?'Wi‑Fi':'BLE')+(enabled?' đã bật.':' đã tắt.'))}
  catch(error){errorText=error.message;message(error.message,true)}
  finally{radioBusy=false;renderHostRadio(hostRadio);if(errorText)$('radioMessage').textContent=errorText}
}
function connection(online){const n=$('connection');n.classList.toggle('offline',!online);n.replaceChildren(el('span','','tiny-dot'),document.createTextNode(online?'Cập nhật trực tiếp':'Đang kết nối lại'))}
function connectLive(){
  if(!state.teacher)return;clearTimeout(reconnectTimer);const old=socket;socket=null;if(old)old.close();
  const ws=new WebSocket((location.protocol==='https:'?'wss':'ws')+'://'+location.host+'/ws/teacher');socket=ws;
  ws.onmessage=e=>{if(socket!==ws)return;try{const data=JSON.parse(e.data);if(data.type==='ready'){connection(true);refresh().catch(err=>message(err.message,true))}if(data.type==='changed')refresh().catch(err=>message(err.message,true))}catch(err){message('Không thể nhận cập nhật trực tiếp.',true)}};
  ws.onclose=event=>{if(socket!==ws)return;connection(false);if(event.code===1008){showAuth('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.');return}if(state.teacher)reconnectTimer=setTimeout(connectLive,5000)};
  ws.onerror=()=>connection(false);
}
$('loginTab').onclick=()=>setAuthMode('login');$('registerTab').onclick=()=>setAuthMode('register');$('switchAuth').onclick=()=>setAuthMode(authMode==='login'?'register':'login');
document.querySelector('.auth-tabs').onkeydown=e=>{if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();setAuthMode(authMode==='login'?'register':'login');$(authMode==='login'?'loginTab':'registerTab').focus()}};
$('togglePassword').onclick=()=>{const show=$('password').type==='password';$('password').type=show?'text':'password';$('togglePassword').setAttribute('aria-label',show?'Ẩn mật khẩu':'Hiện mật khẩu');$('togglePassword').setAttribute('aria-pressed',String(show))};
$('authForm').onsubmit=async e=>{
  e.preventDefault();authError('');
  if(authMode==='register'&&$('password').value!==$('confirmPassword').value){authError('Hai mật khẩu chưa trùng nhau. Vui lòng kiểm tra lại.');$('confirmPassword').focus();return}
  const submit=$('authSubmit');submit.disabled=true;const label=submit.querySelector('span');label.textContent='Đang xử lý…';
  try{const body={email:$('email').value.trim(),password:$('password').value};if(authMode==='register')body.name=$('teacherName').value.trim();const result=await request('/auth/'+authMode,'POST',body);$('password').value='';$('confirmPassword').value='';await enterWorkspace(result.teacher)}
  catch(err){authError(err.message)}
  finally{submit.disabled=false;label.textContent=authMode==='register'?'Tạo tài khoản':'Đăng nhập'}
};
$('logout').onclick=async()=>{const b=$('logout');b.disabled=true;try{await request('/auth/logout','POST');setAuthMode('login');showAuth();history.replaceState(null,'',location.pathname);document.title='NEXUS Classroom · Không gian giảng viên'}catch(e){message(e.message,true)}finally{b.disabled=false}};
function openAccountDialog(){if(!state.teacher)return;$('accountName').value=state.teacher.name;$('accountEmail').value=state.teacher.email;$('accountDialog').showModal();}
$('accountSettings').onclick=openAccountDialog;$('closeAccountDialog').onclick=()=>$('accountDialog').close();$('cancelAccount').onclick=()=>$('accountDialog').close();
$('accountForm').onsubmit=async e=>{e.preventDefault();if(!state.teacher)return;const name=$('accountName').value.trim();if(!name){message('Vui lòng nhập họ và tên.',true);return;}try{const result=await request('/auth/profile','PATCH',{name});state.teacher={...state.teacher,...result.teacher};$('profileName').textContent=state.teacher.name;$('welcomeName').textContent=state.teacher.name.split(/\s+/).at(-1);$('accountDialog').close();message('Đã cập nhật thông tin tài khoản.')}catch(error){message(error.message,true)}};
$('changePassword').onclick=async()=>{if(!state.teacher)return;const current=window.prompt('Nhập mật khẩu hiện tại:');if(current===null)return;const next=window.prompt('Nhập mật khẩu mới (ít nhất 8 ký tự):');if(next===null)return;if(next.trim().length<8){message('Mật khẩu mới phải có ít nhất 8 ký tự.',true);return;}const confirm=window.prompt('Nhập lại mật khẩu mới để xác nhận:');if(confirm===null)return;if(next!==confirm){message('Hai mật khẩu mới không khớp.',true);return;}try{await request('/auth/change-password','POST',{current_password:current,new_password:next});$('accountDialog').close();message('Đã đổi mật khẩu thành công. Vui lòng đăng nhập lại để tiếp tục.');setTimeout(()=>{setAuthMode('login');showAuth();history.replaceState(null,'',location.pathname);document.title='NEXUS Classroom · Không gian giảng viên';},400)}catch(error){message(error.message,true)}};
$('logoutAllDevices').onclick=async()=>{if(!state.teacher)return;if(!window.confirm('Đăng xuất khỏi mọi thiết bị đang truy cập tài khoản này? Bạn sẽ phải đăng nhập lại ở mọi nơi.'))return;try{await request('/auth/logout-all','POST');$('accountDialog').close();message('Đã đăng xuất tài khoản khỏi mọi thiết bị.');setTimeout(()=>{setAuthMode('login');showAuth();history.replaceState(null,'',location.pathname);document.title='NEXUS Classroom · Không gian giảng viên';},400)}catch(error){message(error.message,true)}};
document.querySelectorAll('[data-page],[data-go]').forEach(n=>n.onclick=()=>go(n.dataset.page||n.dataset.go));
$('newExam').onclick=$('heroCreate').onclick=()=>{go('imports');$('examTitle').focus()};
$('mobileMenu').onclick=()=>sidebar(!$('sidebar').classList.contains('is-open'));$('sidebarBackdrop').onclick=()=>sidebar(false);
document.addEventListener('keydown',e=>{if(e.key==='Escape')sidebar(false)});
window.addEventListener('popstate',()=>{if(state.teacher)go(location.hash.slice(1),false)});
window.addEventListener('hashchange',()=>{if(state.teacher)go(location.hash.slice(1),false)});
$('examSearch').oninput=renderExams;$('studentSearch').oninput=renderStudents;
$('examFilters').onclick=e=>{const b=e.target.closest('[data-filter]');if(!b)return;state.filter=b.dataset.filter;document.querySelectorAll('[data-filter]').forEach(n=>n.classList.toggle('active',n===b));renderExams()};
$('resultExamSelect').onchange=()=>{state.exam=$('resultExamSelect').value?Number($('resultExamSelect').value):null;state.question=null;refreshResults().catch(e=>message(e.message,true))};
$('manageContext').onclick=()=>go('management');
$('classSelect').onchange=()=>{state.classId=Number($('classSelect').value)||null;state.courseId=null;state.courses=[];state.exam=null;state.deviceExam=null;state.setupClassId=null;state.setupCourseId=null;if(state.setupStep===3)state.setupStep=2;sessionStorage.removeItem('nexusCourse:'+state.teacher.id);clearCourseData();refresh().catch(e=>message(e.message,true))};
$('courseSelect').onchange=()=>{state.courseId=Number($('courseSelect').value)||null;state.exam=null;state.deviceExam=null;if(state.courseId)sessionStorage.setItem('nexusCourse:'+state.teacher.id,String(state.courseId));else sessionStorage.removeItem('nexusCourse:'+state.teacher.id);clearCourseData();refresh().catch(e=>message(e.message,true))};
document.querySelectorAll('[data-setup-nav],[data-setup-back]').forEach(button=>button.onclick=()=>showSetupStep(Number(button.dataset.setupNav||button.dataset.setupBack)));
$('setupFinish').onclick=()=>{if(!state.students.length){message('Hãy thêm ít nhất một sinh viên trước khi tạo bài thi.',true);return}go('imports');$('examTitle').focus()};
for(const [formId,kind,codeId,nameId] of [['classForm','classes','classCode','className'],['subjectForm','subjects','subjectCode','subjectName']]){
  $(formId).onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;try{const payload={code:$(codeId).value.trim(),name:$(nameId).value.trim()};if(kind==='classes'){if(!state.setupSubjectId)throw Error('Hãy chọn môn học trước.');payload.subject_id=state.setupSubjectId}const item=await request('/'+kind,'POST',payload);e.target.reset();if(kind==='classes'){state.classId=item.id;state.courseId=item.course_id;state.setupClassId=item.id;state.setupCourseId=item.course_id}else{state.setupSubjectId=item.id;state.setupClassId=null;state.setupCourseId=null}await refresh();go('management');showSetupStep(kind==='classes'?3:2);message(kind==='classes'?'Đã tạo lớp. Bây giờ thêm sinh viên vào lớp.':'Đã tạo môn. Bây giờ tạo hoặc chọn lớp.')}catch(error){message(error.message,true)}finally{b.disabled=false}};
}
$('courseForm').onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;try{await request('/classes/'+state.classId+'/courses','POST',{subject_id:Number($('subjectToAdd').value)});await refresh();message('Đã gắn thêm môn vào lớp và đồng bộ danh sách sinh viên.')}catch(error){message(error.message,true)}finally{b.disabled=false}};
$('closeStudentDialog').onclick=$('cancelStudentEdit').onclick=()=>$('studentDialog').close();
$('closeWifiToken').onclick=$('doneWifiToken').onclick=()=>$('wifiTokenDialog').close();
$('radioOpen').onclick=()=>{$('radioDialog').showModal();refreshHostRadio()};
$('closeRadio').onclick=()=>$('radioDialog').close();
$('wifiRadioToggle').onclick=()=>setHostRadio('wifi');
$('bleRadioToggle').onclick=()=>setHostRadio('ble');
$('wifiTokenDialog').onclose=()=>{$('wifiTokenValue').value=''};
$('copyWifiToken').onclick=async()=>{const input=$('wifiTokenValue');try{await navigator.clipboard.writeText(input.value);message('Đã sao chép mã ESP32.')}catch(error){input.select();message('Trình duyệt không cho sao chép tự động. Hãy nhấn Ctrl+C để lấy mã.',true)}};
$('studentEditForm').onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;try{await request('/classes/'+state.classId+'/students/'+$('editStudentId').value,'PATCH',{mssv:$('editMssv').value.trim(),name:$('editName').value.trim(),device_id:$('editDevice').value.trim(),preferred_protocol:$('editProtocol').value,revision:Number($('editStudentRevision').value)});$('studentDialog').close();await refresh();message($('editProtocol').value==='WIFI'?'Đã lưu ESP32. Nếu chưa có token, bấm “Tạo token” tại dòng sinh viên.':'Đã lưu nRF52840. Khi thi hãy xác nhận đúng mã bo.')}catch(error){message(error.message,true)}finally{b.disabled=false}};
$('closeExamDialog').onclick=$('cancelExamEdit').onclick=()=>$('examDialog').close();
$('addExamQuestion').onclick=()=>{$('editQuestions').append(questionEditorCard());renumberEditor()};
$('examEditForm').onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;try{
  const id=$('editExamId').value,revision=Number($('editExamRevision').value),title=$('editExamTitle').value.trim();
  if(state.editorStatus==='draft'){
    const questions=[...$('editQuestions').children].map(card=>{const value={};for(const input of card.querySelectorAll('[data-field]'))value[input.dataset.field]=input.value.trim();return value});
    await request('/exams/'+id,'PUT',{title,revision,questions,time_limit_seconds:$('editTimeLimit').value?Number($('editTimeLimit').value):null});
  }else await request('/exams/'+id,'PATCH',{title,revision});
  $('examDialog').close();await refresh();message('Đã lưu bài thi.');
}catch(error){message(error.message,true)}finally{b.disabled=false}};
function validateFile(file){if(!file)throw Error('Vui lòng chọn file.');if(file.size>10*1024*1024)throw Error('File vượt quá giới hạn 10 MB.');return file}
$('questionFile').onchange=()=>$('questionFileLabel').textContent=$('questionFile').files[0]?.name||'Chọn file Word hoặc PDF';
$('questionImportForm').onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;try{const file=validateFile($('questionFile').files[0]),body=new FormData();body.append('file',file);body.append('title',$('examTitle').value.trim());if($('questionTimeLimit').value)body.append('time_limit_seconds',$('questionTimeLimit').value);const r=await request(scoped('/import/questions'),'POST',body);e.target.reset();$('questionFileLabel').textContent='Chọn file Word hoặc PDF';await refresh();go('exams');message('Đã tạo bài thi “'+r.title+'” với '+r.imported+' câu hỏi.'+(r.time_limit_seconds?' Hẹn giờ '+r.time_limit_seconds+' giây/câu.':''))}catch(err){message(err.message,true)}finally{b.disabled=false}};
$('setupStudentImportForm').onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;try{if(!state.classId)throw Error('Hãy chọn lớp trước khi nhập sinh viên.');const file=validateFile($('setupStudentFile').files[0]),body=new FormData();body.append('file',file);const r=await request('/classes/'+state.classId+'/import/students','POST',body);e.target.reset();await refresh();go('management');showSetupStep(3);const skipped=r.skipped.length?' Bỏ qua '+r.skipped.length+' dòng: '+r.skipped.slice(0,3).join('; ')+(r.skipped.length>3?'; …':''):'';message((r.imported?'Đã nhập '+r.imported+' sinh viên vào lớp.':'Không có sinh viên mới được thêm.')+skipped,r.imported===0)}catch(err){message(err.message,true)}finally{b.disabled=false}};
$('studentForm').onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;try{if(!state.classId)throw Error('Hãy chọn lớp trước khi thêm sinh viên.');await request('/classes/'+state.classId+'/students','POST',{mssv:$('mssv').value,name:$('name').value,device_id:$('device').value,preferred_protocol:$('studentProtocol').value});e.target.reset();updateDeviceHints('add');await refresh();message('Đã thêm sinh viên vào lớp. Có thể thiết lập bo ở mục Sinh viên.')}catch(err){message(err.message,true)}finally{b.disabled=false}};
$('studentProtocol').onchange=()=>updateDeviceHints('add');
$('editProtocol').onchange=()=>updateDeviceHints('edit');
$('questionForm').onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;try{await request(scoped('/questions'),'POST',{text:$('questionText').value,a:$('a').value,b:$('b').value,c:$('c').value,d:$('d').value,correct_choice:$('correct').value,points:Number($('points').value)});e.target.reset();await refresh();message('Đã tạo câu hỏi riêng lẻ.')}catch(err){message(err.message,true)}finally{b.disabled=false}};
$('today').textContent=new Intl.DateTimeFormat('vi-VN',{day:'2-digit',month:'long',year:'numeric'}).format(new Date());
setInterval(tickCountdowns,250);
async function boot(){
  try{const response=await fetch('/api/auth/me',{credentials:'same-origin',signal:AbortSignal.timeout(15000)});if(response.ok){const r=await response.json();await enterWorkspace(r.teacher)}else{showAuth(response.status===401?'':'Không kết nối được với máy chủ. Vui lòng thử lại.')}}
  catch(e){showAuth('Không kết nối được với máy chủ. Vui lòng thử lại.')}
}
boot();
