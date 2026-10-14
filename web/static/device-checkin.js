'use strict';

// Shared check-in for workspace and projector. Wi-Fi boards are chosen by
// device ID; their secret tokens never belong in this form.
window.chooseExamDevices = async function chooseExamDevices(examId) {
  const response = await fetch('/api/exams/' + examId + '/check-in', {
    credentials: 'same-origin', cache: 'no-store'
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw Error(typeof data.detail === 'string' ? data.detail : 'Không tải được danh sách thiết bị.');
  if (!data.students.length) throw Error('Lớp–môn chưa có sinh viên tham gia bài thi.');

  const make = (tag, value = '', className = '') => {
    const node = document.createElement(tag);
    node.textContent = value;
    if (className) node.className = className;
    return node;
  };
  const addOption = (select, label, value) => {
    const option = make('option', label);
    option.value = value;
    select.append(option);
  };
  const wifiBoards = data.devices.filter(board => board.protocol === 'WIFI' && board.wifi_ready);
  const bleBoards = data.devices.filter(board => board.protocol !== 'WIFI' && !board.wifi_ready);
  const onlineBleBoards = bleBoards.filter(board => board.ble_online);
  const dialog = make('dialog', '', 'checkin-dialog');
  const form = make('form');
  form.method = 'dialog';
  const eyebrow = make('span', 'BƯỚC 1 / 2 · GHÉP THIẾT BỊ', 'checkin-eyebrow');
  const title = make('h2', 'Ai dùng bo nào trong lượt thi này?');
  const help = make('p', 'Chọn loại bo rồi chọn đúng mã bo gửi qua BLE (ví dụ STUDENT_001). Bo đã đăng ký được ACCEPT trước giờ thi; NEXT chỉ đến khi câu hỏi mở. ESP32 cần mã đã kích hoạt Wi-Fi.', 'checkin-help');
  const summary = make('p', data.students.length + ' sinh viên · ' +
      onlineBleBoards.length + ' nRF gateway đã thấy · ' +
      wifiBoards.length + ' ESP32 đã cấp mã Wi-Fi', 'checkin-status');
  const rosterNote = make('p', 'Lượt thi có ' + data.students.length +
    ' sinh viên. Web chỉ tự chuyển câu khi tất cả đã nộp; nếu thử vài bo, giảng viên bấm “Chuyển câu tiếp theo” trên màn chiếu.', 'checkin-roster-note');
  rosterNote.hidden = data.students.length <= 2;
  form.append(eyebrow, title, help, summary, rosterNote);

  const list = make('div', '', 'checkin-list');
  const rows = [];
  const usedDefaults = new Set();
  for (const person of data.students) {
    const row = make('div', '', 'checkin-row');
    const identity = make('div', '', 'checkin-person');
    identity.append(make('strong', person.name), make('small', person.mssv));
    const fields = make('div', '', 'checkin-fields');
    const protocolLabel = make('label', '1 · Loại bo');
    const protocol = make('select');
    addOption(protocol, 'nRF52840 · Bluetooth', 'BLE');
    addOption(protocol, 'ESP32 · Wi-Fi', 'WIFI');
    protocol.value = person.preferred_protocol === 'WIFI' ? 'WIFI' : 'BLE';
    protocolLabel.append(protocol);
    const deviceLabel = make('label', '2 · Mã bo');
    const device = make('select');
    const manual = make('input');
    manual.type = 'text';
    manual.maxLength = 40;
    manual.autocomplete = 'off';
    manual.placeholder = 'VD: STUDENT_001 hoặc BLE-001';
    manual.hidden = true;
    deviceLabel.append(device, manual);
    const status = make('p', '', 'checkin-device-status');
    fields.append(protocolLabel, deviceLabel, status);
    row.append(identity, fields);
    list.append(row);

    const suggestion = (person.device_id || '').trim();
    let ownsDefault = false;
    const updateStatus = () => {
      const isWifi = protocol.value === 'WIFI';
      manual.hidden = isWifi || device.value !== '__manual__';
      const picked = !manual.hidden ? manual.value.trim() : device.value;
      if (isWifi) {
        status.textContent = !wifiBoards.length ? 'Chưa có ESP32. Vào Sinh viên → Thiết lập → Tạo token trước.' :
          picked ? 'Mã Wi-Fi đã cấp. Bo sẽ hiện kết nối khi câu hỏi mở.' : 'Chọn mã ESP32, không dán token.';
      } else {
        const known = bleBoards.find(board => board.device_id === picked);
        status.textContent = !picked ? 'Chọn bo đang kết nối, hoặc nhập mã nRF khác.' :
          known?.ble_online ? 'Gateway đã thấy bo' + (known.ble_authorized ? '; đã gửi ACCEPT, LED Connect phải sáng.' : '; chưa ACCEPT, kiểm tra mã bo đã đăng ký.') : 'Chưa thấy tín hiệu BLE; kiểm tra firmware hoặc bật bo.';
      }
      status.classList.toggle('ready', Boolean(picked && (isWifi ||
        bleBoards.some(board => board.device_id === picked && board.ble_online))));
    };
    const setOptions = () => {
      const isWifi = protocol.value === 'WIFI';
      const boards = isWifi ? wifiBoards : onlineBleBoards;
      device.replaceChildren();
      addOption(device, isWifi ? 'Chọn ESP32 đã kích hoạt' : 'Chọn mã nRF', '');
      for (const board of boards) addOption(device, board.device_id +
        (isWifi ? ' · đã cấp token' : board.ble_online ? (board.ble_authorized ? ' · đã ACCEPT' : ' · chưa ACCEPT') : ' · chưa có tín hiệu'), board.device_id);
      if (!isWifi) {
        if (suggestion && !boards.some(board => board.device_id === suggestion))
          addOption(device, suggestion + ' · mã gợi ý', suggestion);
        addOption(device, 'Nhập mã nRF khác…', '__manual__');
      }
      const key = suggestion.toLocaleLowerCase('vi');
      if (suggestion && (!usedDefaults.has(key) || ownsDefault) && (boards.some(board => board.device_id === suggestion) ||
          (!isWifi && Array.from(device.options).some(option => option.value === suggestion)))) {
        device.value = suggestion;
        usedDefaults.add(key);
        ownsDefault = true;
      }
      manual.value = '';
      updateStatus();
    };
    protocol.onchange = setOptions;
    device.onchange = () => {updateStatus(); if (!manual.hidden) manual.focus()};
    manual.oninput = updateStatus;
    setOptions();
    rows.push({person, protocol, device, manual, row});
  }
  form.append(list);
  const review = make('div', '', 'checkin-review');
  review.hidden = true;
  form.append(review);
  const error = make('p', '', 'checkin-error');
  error.setAttribute('role', 'alert');
  error.hidden = true;
  form.append(error);
  const actions = make('div', '', 'checkin-actions');
  const cancel = make('button', 'Hủy', 'secondary');
  cancel.type = 'button';
  const confirm = make('button', 'Bước 2 · Xác nhận & bắt đầu', 'primary');
  confirm.type = 'submit';
  actions.append(cancel, confirm);
  form.append(actions);
  dialog.append(form);
  document.body.append(dialog);

  return new Promise(resolve => {
    let selected = null;
    let reviewing = false;
    let pendingAssignments = [];
    cancel.onclick = () => {
      if (!reviewing) {dialog.close();return}
      reviewing = false;
      review.hidden = true;
      list.hidden = false;
      summary.hidden = false;
      rosterNote.hidden = data.students.length <= 2;
      eyebrow.textContent = 'BƯỚC 1 / 2 · GHÉP THIẾT BỊ';
      title.textContent = 'Ai dùng bo nào trong lượt thi này?';
      help.textContent = 'Chọn loại bo rồi chọn đúng ID bo gửi qua BLE. LED Connect sáng sau ACCEPT ngay cả trước giờ thi; LED Sent chỉ nháy sau NEXT. ESP32 cần mã đã kích hoạt Wi-Fi.';
      cancel.textContent = 'Hủy';
      confirm.textContent = 'Bước 2 · Xác nhận & bắt đầu';
    };
    form.onsubmit = event => {
      event.preventDefault();
      if (reviewing) {
        selected = {revision:data.exam.revision, assignments:pendingAssignments};
        dialog.close();
        return;
      }
      error.hidden = true;
      const assignments = rows.map(({person, protocol, device, manual}) => ({
        student_id: person.id, protocol: protocol.value,
        device_id: protocol.value === 'BLE' && device.value === '__manual__' ? manual.value.trim() : device.value
      }));
      const missing = assignments.find(item => !item.device_id);
      const seen = new Set();
      const duplicate = assignments.find(item => {
        const key = item.device_id.toLocaleLowerCase('vi');
        if (seen.has(key)) return true;
        seen.add(key);
        return false;
      });
      const bad = missing || duplicate;
      if (bad) {
        error.textContent = missing ? 'Hãy chọn mã bo cho từng sinh viên. ESP32 cần mã đã kích hoạt Wi-Fi.' :
          'Mã ' + duplicate.device_id + ' đang gán cho hai sinh viên. Mỗi bo chỉ dùng cho một người trong lượt này.';
        error.hidden = false;
        rows.find(item => item.person.id === bad.student_id).row.scrollIntoView({block:'nearest'});
        return;
      }
      const bleOffline = assignments.filter(item => item.protocol === 'BLE' &&
        !bleBoards.some(board => board.device_id === item.device_id && board.ble_online));
      pendingAssignments = assignments;
      review.replaceChildren(make('p', 'Kiểm tra lần cuối: mỗi sinh viên đang cầm đúng bo bên dưới. Bấm bắt đầu sẽ mở câu 1 ngay.', 'checkin-help'));
      for (const assignment of assignments) {
        const person = rows.find(item => item.person.id === assignment.student_id).person;
        const line = make('div', '', 'checkin-review-row');
        line.append(make('strong', person.name + ' · ' + person.mssv),
          make('span', (assignment.protocol === 'WIFI' ? 'ESP32 · Wi-Fi' : 'nRF52840 · BLE') + ' — ' + assignment.device_id));
        review.append(line);
      }
      if (bleOffline.length) review.append(make('p', bleOffline.length +
        ' nRF chưa thấy tín hiệu BLE. Có thể bật bo trước khi bắt đầu hoặc quay lại chọn mã khác.', 'checkin-roster-note'));
      reviewing = true;
      list.hidden = true;
      summary.hidden = true;
      rosterNote.hidden = true;
      review.hidden = false;
      eyebrow.textContent = 'BƯỚC 2 / 2 · XÁC NHẬN';
      title.textContent = 'Sẵn sàng mở câu 1?';
      help.textContent = assignments.length + ' sinh viên · ' +
        assignments.filter(item => item.protocol === 'BLE').length + ' nRF · ' +
        assignments.filter(item => item.protocol === 'WIFI').length + ' ESP32';
      cancel.textContent = '← Quay lại';
      confirm.textContent = 'Bắt đầu & trình chiếu';
    };
    dialog.onclose = () => {dialog.remove();resolve(selected)};
    dialog.showModal();
  });
};
