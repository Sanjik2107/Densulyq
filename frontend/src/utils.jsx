export const API_BASE = import.meta.env.VITE_API_BASE_URL || window.location.origin
export const AUTH_STORAGE_KEY = 'densaulyq-auth-v2'

export const I18N_MAP = {
  'готово':'ready','назначен':'ordered','проверено':'reviewed',
  'в обработке':'processing','ожидание':'pending','подтверждено':'confirmed','отменено':'cancelled',
  'активно':'active','выполнено':'completed','Кабинет':'Room',
  'Терапевт':'Therapist','Кардиолог':'Cardiologist','Невролог':'Neurologist',
  'Эндокринолог':'Endocrinologist','Гастроэнтеролог':'Gastroenterologist',
  'Офтальмолог':'Ophthalmologist','ЛОР':'ENT','Дерматолог':'Dermatologist',
  'Уролог':'Urologist','Хирург':'Surgeon',
  'Общий анализ крови':'Complete blood count','Биохимия крови':'Blood biochemistry',
  'Анализ мочи':'Urinalysis','ЭКГ':'ECG','УЗИ брюшной полости':'Abdominal ultrasound',
  'Консультация кардиолога':'Cardiologist consultation','Холестерин общий':'Total cholesterol',
  'Гемоглобин':'Hemoglobin','Эритроциты':'Erythrocytes','Лейкоциты':'Leukocytes',
  'Тромбоциты':'Platelets','Глюкоза':'Glucose','Холестерин':'Cholesterol',
  'АЛТ':'ALT','АСТ':'AST','Билирубин':'Bilirubin','Белок':'Protein',
  'Отс.':'Not detected','г/л':'g/L','ммоль/л':'mmol/L','Ед/л':'U/L',
  'мкмоль/л':'umol/L','×10¹²/л':'×10¹²/L','×10⁹/л':'×10⁹/L',
}

export const ANALYSIS_NAME_OPTIONS = [
  'Complete blood count','Blood biochemistry','Urinalysis','ECG',
  'Thyroid panel','Lipid panel','Liver panel','Vitamin D',
]

export const ANALYSIS_STATUS_OPTIONS = [
  { value: 'назначен', label: 'Ordered' },
  { value: 'в обработке', label: 'Processing' },
  { value: 'готово', label: 'Ready' },
]

const ANALYSIS_STATUS_TRANSITIONS = {
  'назначен': ['назначен', 'в обработке'],
  'в обработке': ['в обработке', 'готово'],
  'готово': ['готово'],
  'проверено': ['проверено'],
}

export function getAnalysisStatusOptions(currentStatus) {
  const allowed = ANALYSIS_STATUS_TRANSITIONS[currentStatus] || [currentStatus].filter(Boolean)
  return ANALYSIS_STATUS_OPTIONS.filter(option => allowed.includes(option.value))
}

export function t(value) {
  if (value == null) return value
  let out = String(value)
  Object.entries(I18N_MAP).forEach(([ru, en]) => { out = out.split(ru).join(en) })
  return out
}

export function getInitials(fullName) {
  if (!fullName) return 'PT'
  const parts = fullName.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[1][0]).toUpperCase()
}

export function normalizeDate(rawValue) {
  if (!rawValue) return ''
  if (/^\d{4}-\d{2}-\d{2}$/.test(rawValue)) return rawValue
  const parts = rawValue.split('.')
  if (parts.length === 3) return parts[2] + '-' + parts[1].padStart(2,'0') + '-' + parts[0].padStart(2,'0')
  return rawValue
}

export function monthShort(isoDate) {
  if (!isoDate) return '---'
  const date = new Date(isoDate + 'T00:00:00')
  if (Number.isNaN(date.getTime())) return '---'
  return date.toLocaleDateString('ru-RU', {month:'short'}).replace('.','')
}

function appointmentTimestamp(isoDate, time) {
  if (!isoDate) return 0
  const safeTime = /^\d{2}:\d{2}$/.test(time || '') ? time : '00:00'
  const date = new Date(`${isoDate}T${safeTime}:00`)
  return Number.isNaN(date.getTime()) ? 0 : date.getTime()
}

export function isUpcomingActiveAppointment(item) {
  if (!item || item.status === 'cancelled') return false
  const timestamp = item.timestamp || appointmentTimestamp(item.dateISO, item.time)
  return timestamp >= Date.now()
}

function sortAppointmentsForDisplay(items) {
  return [...items].sort((a, b) => {
    const aUpcoming = isUpcomingActiveAppointment(a)
    const bUpcoming = isUpcomingActiveAppointment(b)
    if (aUpcoming !== bUpcoming) return aUpcoming ? -1 : 1
    if (aUpcoming && bUpcoming) return a.timestamp - b.timestamp
    return b.timestamp - a.timestamp
  })
}

export function getAnalysisDisplayDate(item) {
  return normalizeDate(item.ready_at || item.scheduled_for || item.date || item.ordered_at || '')
}

export function formatDateInputValue(date) {
  return [date.getFullYear(), String(date.getMonth()+1).padStart(2,'0'), String(date.getDate()).padStart(2,'0')].join('-')
}

export function getLocalDateIso(offsetDays = 0) {
  const date = new Date()
  date.setHours(0,0,0,0)
  date.setDate(date.getDate() + offsetDays)
  return formatDateInputValue(date)
}

export function getDefaultBookingDate() {
  const now = new Date()
  const minutes = now.getHours() * 60 + now.getMinutes()
  return getLocalDateIso(minutes >= (17*60+45) ? 1 : 0)
}

export function badgeForStatus(status) {
  if (['ready','reviewed','confirmed','active'].includes(status)) return 'b-green'
  if (['processing','pending'].includes(status)) return 'b-warn'
  if (['ordered'].includes(status)) return 'b-gray'
  if (['inactive', 'cancelled'].includes(status)) return 'b-red'
  return 'b-gray'
}

export function getRoleChip(role) {
  const cls = role === 'admin' ? 'admin' : role === 'doctor' ? 'doctor' : role === 'lab' ? 'lab' : 'user'
  const label = role === 'admin' ? 'Admin' : role === 'doctor' ? 'Doctor' : role === 'lab' ? 'Lab' : 'Patient'
  return <span className={`role-chip ${cls}`}>{label}</span>
}

export function formatRole(role) {
  if (role === 'admin') return 'Admin'
  if (role === 'doctor') return 'Doctor'
  if (role === 'lab') return 'Lab'
  return 'Patient'
}

export function sortByDateDesc(items, key) {
  return [...items].sort((a,b) => normalizeDate(b[key]).localeCompare(normalizeDate(a[key])))
}
export function sortByDateAsc(items, key) {
  return [...items].sort((a,b) => normalizeDate(a[key]).localeCompare(normalizeDate(b[key])))
}

export function mapUser(user) {
  const u = user || {}
  return {
    id: u.id ?? 1,
    name: u.name || 'Patient',
    username: u.username || '',
    initials: getInitials(u.name || 'Patient'),
    dob: u.dob || '',
    iin: u.iin || '',
    blood: u.blood_type || '',
    phone: u.phone || '',
    email: u.email || '',
    address: u.address || '',
    height: u.height ?? '',
    weight: u.weight ?? '',
    role: u.role || 'user',
    department: u.department || '',
    is_active: u.is_active !== false,
    email_verified: u.email_verified === true,
    phone_verified: u.phone_verified === true,
    two_factor_enabled: u.two_factor_enabled === true,
  }
}

export function mapAnalysesList(analyses) {
  return sortByDateDesc((analyses || []).map(item => ({
    id: item.id,
    name: t(item.name),
    date: getAnalysisDisplayDate(item) || item.date || '—',
    doctor: t(item.doctor),
    status: t(item.status || ''),
    statusRaw: item.status || '',
    orderedAt: normalizeDate(item.ordered_at || ''),
    scheduledFor: normalizeDate(item.scheduled_for || ''),
    readyAt: normalizeDate(item.ready_at || ''),
    reviewedAt: normalizeDate(item.reviewed_at || ''),
    doctorNote: t(item.doctor_note || ''),
    labNote: t(item.lab_note || ''),
    isVisibleToPatient: item.is_visible_to_patient !== false,
    patientName: t(item.patient_name || ''),
    patientUsername: t(item.patient_username || ''),
    results: (item.results || []).map(r => ({...r, param:t(r.param), unit:t(r.unit), norm:t(r.norm), val:t(r.val)})),
  })), 'date')
}

export function mapAppointmentsList(appointments) {
  return sortAppointmentsForDisplay((appointments || []).map(item => {
    const iso = normalizeDate(item.date)
    const status = t(item.status || 'pending')
    const timestamp = appointmentTimestamp(iso, item.time)
    return {
      id: item.id,
      doctor: t(item.doctor),
      spec: t(item.speciality || item.doctor),
      day: iso ? iso.split('-')[2] : '--',
      mon: monthShort(iso),
      time: item.time || '--:--',
      place: t(item.place || 'TBD'),
      status,
      statusRaw: item.status || '',
      dateISO: iso,
      timestamp,
    }
  }).map(item => ({ ...item, isUpcomingActive: isUpcomingActiveAppointment(item) })))
}

export function mapReferralsList(referrals) {
  return sortByDateDesc((referrals || []).map(item => ({
    id: item.id,
    name: t(item.name),
    from: t(item.from_doctor),
    date: item.issue_date,
    deadline: item.deadline,
    status: t(item.status),
  })), 'date')
}

export function formatAnalysisResultsText(results) {
  return (results || []).map(r => [r.param||'',r.val||'',r.unit||'',r.norm||'',r.ok?'ok':'abnormal'].join(' | ')).join('\n')
}

export function parseAnalysisResultsText(raw) {
  const text = String(raw || '').trim()
  if (!text) return []
  return text.split('\n').map((line, index) => {
    const parts = line.split('|').map(p => p.trim())
    if (parts.length < 5) throw new Error(`Line ${index+1}: use format Parameter | Value | Unit | Range | ok/abnormal`)
    const flag = parts[4].toLowerCase()
    if (!['ok','abnormal','high','low','normal','out'].includes(flag)) throw new Error(`Line ${index+1}: last value must be ok or abnormal`)
    return {param:parts[0], val:parts[1], unit:parts[2], norm:parts[3], ok:['ok','normal'].includes(flag)}
  })
}
