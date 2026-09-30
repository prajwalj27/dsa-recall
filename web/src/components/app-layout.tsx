import { ChartLine, House, ListChecks, Network, Settings } from 'lucide-react'
import { useEffect } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router'

import { ProblemPanel } from '@/components/problem-panel'
import { SyncBanner } from '@/components/sync-banner'
import { SyncControl } from '@/components/sync-control'
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
} from '@/components/ui/sidebar'
import { useToday } from '@/lib/queries'

const NAV = [
  { to: '/', label: 'Today', icon: House },
  { to: '/skill-tree', label: 'Skill tree', icon: Network },
  { to: '/solved', label: 'Solved', icon: ListChecks },
  { to: '/insights', label: 'Insights', icon: ChartLine },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export function AppLayout() {
  const { pathname } = useLocation()
  const { data: today } = useToday()
  const dueCount = today?.due.total_due ?? 0

  // The due count in the tab title (design doc: always visible).
  useEffect(() => {
    document.title = dueCount > 0 ? `(${dueCount}) DSA Recall` : 'DSA Recall'
  }, [dueCount])

  return (
    <SidebarProvider>
      <Sidebar>
        <SidebarHeader className="px-4 py-3 text-lg font-semibold">DSA Recall</SidebarHeader>
        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupContent>
              <SidebarMenu>
                {NAV.map(({ to, label, icon: Icon }) => (
                  <SidebarMenuItem key={to}>
                    <SidebarMenuButton asChild isActive={pathname === to}>
                      <NavLink to={to}>
                        <Icon />
                        <span>{label}</span>
                      </NavLink>
                    </SidebarMenuButton>
                    {to === '/' && dueCount > 0 ? (
                      <SidebarMenuBadge aria-label={`${dueCount} due`}>{dueCount}</SidebarMenuBadge>
                    ) : null}
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>
      </Sidebar>
      <SidebarInset>
        <header className="flex h-14 items-center gap-2 border-b px-4">
          <SidebarTrigger />
          <div className="ml-auto">
            <SyncControl />
          </div>
        </header>
        <SyncBanner />
        <main className="flex-1 p-4 sm:p-6">
          <Outlet />
        </main>
      </SidebarInset>
      <ProblemPanel />
    </SidebarProvider>
  )
}
