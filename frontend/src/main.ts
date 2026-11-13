import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { initAuth } from './lib/auth'
import { warmUpBackend } from './lib/api'
import './style.css'

document.title = import.meta.env.VITE_CLUB_NAME || '토론 동아리'
warmUpBackend()
void initAuth()

createApp(App).use(router).mount('#app')
