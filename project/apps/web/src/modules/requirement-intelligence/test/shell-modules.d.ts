// The shell is plain JavaScript; these are the few things its tests (shell.test.tsx) use.
declare module '*/Layouts/Sidebar' {
  import type { ComponentType } from 'react'
  const Sidebar: ComponentType<{ collapsed: boolean; onToggle: () => void }>
  export default Sidebar
}
declare module '*/routes/AppRoutes' {
  import type { ComponentType } from 'react'
  const AppRoutes: ComponentType
  export default AppRoutes
}
declare module '*/data/navigation' {
  export interface NavItem {
    type?: string
    label?: string
    path?: string
    expandable?: boolean
    children?: NavItem[]
  }
  export const navigation: NavItem[]
}
