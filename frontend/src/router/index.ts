import { createRouter, createWebHistory, type RouteLocationNormalized } from 'vue-router'
import HomePage from '../views/HomePage.vue'
import WishList from '../views/WishList.vue'
import ExplorePage from '../views/ExplorePage.vue'
import RecommendationsPage from '../views/RecommendationsPage.vue'
import GameDetail from '../views/GameDetail.vue'

const routes = [
  { path: '/', name: 'home', component: HomePage },
  { path: '/wishlist/:id?', name: 'wishlist', component: WishList, props: true },
  { path: '/explore/:id?', name: 'explore', component: ExplorePage, props: true },
  {
    path: '/game/:id/:gameId',
    name: 'game',
    component: GameDetail,
    props: (route: RouteLocationNormalized) => ({
      id: route.params.id as string,
      gameId: Number(route.params.gameId),
      explanationStyle: route.params.explanationStyle,
    }),
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
