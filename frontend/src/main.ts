import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './styles/theme.css'
import { Icon } from '@iconify/vue'
import { createPinia } from 'pinia'

const app = createApp(App)

app.use(router)
app.use(createPinia())

// Register Icon component globally
app.component('Icon', Icon)

app.mount('#app')
