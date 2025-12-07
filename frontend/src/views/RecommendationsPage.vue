<script lang="ts" setup>
import { RouterLink, useRouter } from 'vue-router'
import RecommendationCard from '@/components/RecommendationCard.vue'
import type { Recommendation } from '@/recommendation.mjs'
import { onMounted, ref } from 'vue'
import * as api from '@/api.mjs'

interface Props {
  id: string
  explanationStyle: 'references' | 'features'
}

const props = defineProps<Props>()

// const exampleRecommendation = {
//   boardgame: {
//     id: '1',
//     title: 'Catan',
//     description: 'A game of trading and building.',
//     mechanics: ['Trading', 'Building', 'Dice Rolling'],
//     genre: ['Strategy', 'Family'],
//     themes: ['Economic', 'Negotiation'],
//     min_players: 3,
//     max_players: 4,
//     complexity: 2.5,
//     age_recommendation: 10,
//     num_user_ratings: 5000,
//     avg_user_rating: 4.2,
//     year_published: 1995,
//     playing_time_minutes: 60,
//     image_url:
//       'https://cf.geekdo-images.com/0XODRpReiZBFUffEcqT5-Q__imagepage/img/enC7UTvCAnb6j1Uazvh0OBQjvxw=/fit-in/900x600/filters:no_upscale():strip_icc()/pic9156909.png',
//     bgg_url: 'https://boardgamegeek.com/boardgame/13/catan',
//   },
//   explanation: {
//     references: ['Uno', 'Monopoly'],
//     features: ['Trading', 'Building'],
//   },
// }

onMounted(() => {
  fetchRecommendations(props.id)
})

const recommendations = ref<Recommendation[]>([])
const router = useRouter()

const fetchRecommendations = async (session_id: string) => {
  recommendations.value = await api.getSessionRecommendations(session_id)
}

const viewgame = (gameId: string) => {
  // navigate to game detail page
  router.push(`/game/${props.id}/${gameId}`)
}
</script>

<template>
  <nav class="navbar">
    <RouterLink to="/"><img src="../assets/home.svg" alt="Home" class="icon" /></RouterLink
    ><RouterLink to="/wishlist"
      ><img src="../assets/wishlist.svg" alt="Wishlist" class="icon"
    /></RouterLink>
  </nav>
  <div>
    <h1>Recommended for you:</h1>
    <RecommendationCard
      v-for="rec in recommendations"
      :key="rec.boardgame.id"
      :recommendation="rec"
      :explanationStyle="rec.explanation.type"
      size="large"
      @viewgame="viewgame"
    />
  </div>
  <div class="floating-footer">
    <button class="floating-button">
      <RouterLink :to="'/explore/' + props.id">Change Preferences</RouterLink>
    </button>
  </div>
</template>

<style scoped>
.floating-footer {
  position: fixed;
  background-color: white;
  border-top: black solid 1px;
  bottom: 0;
  left: 0;
  width: 100%;
}

.floating-button {
  border: black 1px solid;
  border-radius: 8px;
  margin: 10px auto;
  padding: 20px auto;
  width: 250px;
  text-align: center;
  font-size: large;
  font-weight: bold;
  color: black;
  cursor: pointer;
  display: block;
  height: 30px;
}
</style>
