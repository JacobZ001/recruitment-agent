import { Navigate, createBrowserRouter } from 'react-router-dom'
import { AppLayout } from '@/components/AppLayout'
import { CandidateDetailPage } from '@/pages/CandidateDetailPage'
import { CandidateListPage } from '@/pages/CandidateListPage'

export const router = createBrowserRouter(
  [
    {
      path: '/',
      element: <AppLayout />,
      children: [
        { index: true, element: <CandidateListPage /> },
        { path: 'candidates/:candidateId', element: <CandidateDetailPage /> },
      ],
    },
    { path: '*', element: <Navigate to="/" replace /> },
  ],
  { basename: '/app' },
)
