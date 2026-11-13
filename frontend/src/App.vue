<script setup lang="ts">
import { RouterLink, RouterView, useRouter } from 'vue-router'
import { logout, useAuth } from '@/lib/auth'

const clubName = import.meta.env.VITE_CLUB_NAME || '토론 동아리'
const { user, isLoggedIn, isAdmin, isReady, mustChangePassword } = useAuth()
const router = useRouter()

async function onLogout() {
  await logout()
  await router.push({ name: 'home' })
}
</script>

<template>
  <header class="topbar">
    <div class="topbar-inner">
      <RouterLink class="brand" to="/home">{{ clubName }}</RouterLink>
      <nav v-if="!mustChangePassword" class="nav" aria-label="주 메뉴">
        <RouterLink to="/reservation">동아리방 예약</RouterLink>
        <RouterLink to="/timer">타이머</RouterLink>
        <RouterLink to="/record">토론 기록</RouterLink>
        <RouterLink v-if="isAdmin" to="/admin/members">회원 관리</RouterLink>
      </nav>
      <div class="account">
        <template v-if="isLoggedIn">
          <RouterLink v-if="!mustChangePassword" to="/mypage">{{ user?.name }}</RouterLink>
          <button class="btn btn-sm" type="button" @click="onLogout">로그아웃</button>
        </template>
        <template v-else>
          <RouterLink class="btn btn-sm" to="/signup">회원가입</RouterLink>
          <RouterLink class="btn btn-sm btn-primary" to="/login">로그인</RouterLink>
        </template>
      </div>
    </div>
  </header>
  <main>
    <RouterView v-if="isReady" />
    <p v-else class="empty">불러오는 중…</p>
  </main>
</template>

<style scoped>
.topbar { background: var(--surface); border-bottom: 1px solid var(--border); position: sticky; top: 0; z-index: 10; }
.topbar-inner { max-width: 1080px; margin: 0 auto; padding: 10px 16px; display: flex; align-items: center; gap: 20px; flex-wrap: wrap; }
.brand { font-weight: 700; font-size: 17px; color: var(--text); }
.nav { display: flex; gap: 4px; flex: 1 1 auto; flex-wrap: wrap; }
.nav a { color: var(--muted); padding: 6px 10px; border-radius: 8px; }
.nav a.router-link-active { color: var(--primary); background: var(--primary-soft); font-weight: 600; }
.account { display: flex; align-items: center; gap: 10px; margin-left: auto; }
</style>
