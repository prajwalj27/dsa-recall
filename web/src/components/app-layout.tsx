import { ChartLine, House, ListChecks, Network, RefreshCw, Settings } from 'lucide-react'
import { NavLink, Outlet, useLocation } from 'react-router'

import { Button } from '@/components/ui/button'
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

const NAV = [
  { to: '/', label: 'Today', icon: House },
  { to: '/skill-tree', label: 'Skill tree', icon: Network },
  { to: '/solved', label: 'Solved', icon: ListChecks },
  { to: '/insights', label: 'Insights', icon: ChartLine },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export function AppLayout() {
  const { pathname } = useLocation()
  const dueCount = 0 // TODO: from the reviews API (build step 1)

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
                    {to === '/' && dueCount > 0 && <SidebarMenuBadge>{dueCount}</SidebarMenuBadge>}
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
          <div className="ml-auto flex items-center gap-3 text-sm text-muted-foreground">
            <span>Last synced: never</span>
            <Button size="sm" variant="outline" disabled>
              <RefreshCw />
              Sync
            </Button>
          </div>
        </header>
        <main className="flex-1 p-6">
          <Outlet />
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}
