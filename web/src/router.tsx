import { createBrowserRouter } from 'react-router'

import { AppLayout } from '@/components/app-layout'
import { PlaceholderPage } from '@/pages/placeholder'
import { TodayPage } from '@/pages/today'

export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { index: true, element: <TodayPage /> },
      {
        path: 'skill-tree',
        element: <PlaceholderPage title="Skill tree" description="Your brain map (build step 4)." />,
      },
      {
        path: 'solved',
        element: <PlaceholderPage title="Solved" description="Every problem you've solved (build step 3)." />,
      },
      {
        path: 'insights',
        element: <PlaceholderPage title="Insights" description="Trends and weekly summary (build step 5)." />,
      },
      {
        path: 'settings',
        element: <PlaceholderPage title="Settings" description="Connections, models, daily target (build step 5)." />,
      },
    ],
  },
])
