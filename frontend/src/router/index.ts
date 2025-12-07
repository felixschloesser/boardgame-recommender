import { createRouter, createWebHistory } from 'vue-router'
import HomePage from '../views/HomePage.vue'
import WishList from '../views/WishList.vue'
import ExplorePage from '../views/ExplorePage.vue'
import RecommendationsPage from '../views/RecommendationsPage.vue'
import GameDetail from '../views/GameDetail.vue'

const routes = [
  { path: '/', name: 'home', component: HomePage },
  { path: '/wishlist', name: 'wishlist', component: WishList },
  { path: '/explore/:id?', name: 'explore', component: ExplorePage, props: true },
  {
    path: '/game/:id/:gameid',
    name: 'game',
    component: GameDetail,
    props: true,
  },
  {
    path: '/recommendations/:id',
    name: 'recommendations',
    component: RecommendationsPage,
    props: true,
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: routes,
})

export default router
