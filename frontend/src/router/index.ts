import { createRouter, createWebHistory } from 'vue-router'
import { initAuth, useAuth } from '@/lib/auth'

declare module 'vue-router' {
  interface RouteMeta {
    /** 로그인 없이 볼 수 있는 화면 */
    public?: boolean
    /** 관리자 전용 */
    admin?: boolean
  }
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/home' },
    { path: '/home', name: 'home', component: () => import('@/views/HomeView.vue'), meta: { public: true } },
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
    { path: '/signup', name: 'signup', component: () => import('@/views/SignupView.vue'), meta: { public: true } },
    { path: '/timer', name: 'timer', component: () => import('@/views/TimerView.vue'), meta: { public: true } },
    { path: '/change-password', name: 'change-password', component: () => import('@/views/ChangePasswordView.vue') },
    { path: '/reservation', name: 'reservation', component: () => import('@/views/ReservationView.vue') },
    { path: '/record', name: 'record', component: () => import('@/views/RecordView.vue') },
    { path: '/mypage', name: 'mypage', component: () => import('@/views/MyPageView.vue') },
    {
      path: '/record/manage',
      name: 'debate-manage',
      component: () => import('@/views/DebateManageView.vue'),
      meta: { admin: true },
    },
    {
      path: '/admin/members',
      name: 'admin-members',
      component: () => import('@/views/AdminMembersView.vue'),
      meta: { admin: true },
    },
    { path: '/:pathMatch(.*)*', redirect: '/home' },
  ],
})

// 화면 이동 제한은 편의 기능입니다. 실제 권한 검사는 서버가 모든 요청에서 다시 합니다.
router.beforeEach(async (to) => {
  await initAuth()
  const { isLoggedIn, isAdmin, mustChangePassword } = useAuth()

  if (isLoggedIn.value && mustChangePassword.value && to.name !== 'change-password') {
    return { name: 'change-password' }
  }
  if (to.meta.public) return true
  if (!isLoggedIn.value) return { name: 'login', query: { next: to.fullPath } }
  if (to.meta.admin && !isAdmin.value) return { name: 'home' }
  return true
})

export default router
