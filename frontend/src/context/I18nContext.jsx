import { createContext, useContext, useMemo, useState } from 'react'

const DICT = {
  en: {
    dashboard: 'Dashboard', analyses: 'Analysis results', referrals: 'Referrals',
    appointments: 'Appointments', ai: 'AI Assistant', profile: 'My profile',
    patients: 'Patients', admin: 'Admin panel', lab: 'Lab workspace',
    overview: 'Overview', records: 'Medical records', visits: 'Visits',
    clinical: 'Clinical', management: 'Management', account: 'Account',
    laboratory: 'Laboratory', logout: 'Logout', themeLight: 'Light', themeDark: 'Dark',
    newUser: '+ New user', refreshPatients: 'Refresh patients',
  },
  ru: {
    dashboard: 'Панель', analyses: 'Анализы', referrals: 'Направления',
    appointments: 'Записи', ai: 'AI ассистент', profile: 'Профиль',
    patients: 'Пациенты', admin: 'Админ-панель', lab: 'Лаборатория',
    overview: 'Обзор', records: 'Медкарта', visits: 'Визиты',
    clinical: 'Клиника', management: 'Управление', account: 'Аккаунт',
    laboratory: 'Лаборатория', logout: 'Выйти', themeLight: 'Светлая', themeDark: 'Тёмная',
    newUser: '+ Новый пользователь', refreshPatients: 'Обновить пациентов',
  },
  kz: {
    dashboard: 'Бақылау', analyses: 'Талдаулар', referrals: 'Жолдамалар',
    appointments: 'Қабылдаулар', ai: 'AI көмекші', profile: 'Профиль',
    patients: 'Пациенттер', admin: 'Админ панелі', lab: 'Зертхана',
    overview: 'Шолу', records: 'Медкарта', visits: 'Қабылдау',
    clinical: 'Клиника', management: 'Басқару', account: 'Аккаунт',
    laboratory: 'Зертхана', logout: 'Шығу', themeLight: 'Жарық', themeDark: 'Қараңғы',
    newUser: '+ Жаңа қолданушы', refreshPatients: 'Пациенттерді жаңарту',
  },
}

const I18nContext = createContext(null)

export function I18nProvider({ children }) {
  const [lang, setLang] = useState(() => {
    try { return localStorage.getItem('densaulyq-lang') || 'en' } catch { return 'en' }
  })
  const value = useMemo(() => ({
    lang,
    setLang: (next) => {
      const safe = DICT[next] ? next : 'en'
      try { localStorage.setItem('densaulyq-lang', safe) } catch { return }
      setLang(safe)
    },
    tr: (key) => DICT[lang]?.[key] || DICT.en[key] || key,
  }), [lang])
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export const useI18n = () => useContext(I18nContext)
