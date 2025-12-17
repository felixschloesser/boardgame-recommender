<script lang="ts" setup>
import { RouterLink, useRouter } from 'vue-router'
import RecommendationCard from '@/components/RecommendationCard.vue'
import type { Recommendation } from '@/recommendation.mjs'
import { onMounted, ref } from 'vue'
import * as api from '@/api.mjs'

interface Props {
  id: string
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

const viewgame = (gameId: number) => {
  // navigate to game detail page
  router.push(`/game/${props.id}/${gameId}`)
}
</script>

<template>
  <nav class="navbar">
    <RouterLink to="/"><Icon class="icon-btn" icon="material-symbols:home-rounded" /></RouterLink
    ><RouterLink :to="`/wishlist/${props.id}`"
      ><Icon class="icon-btn" icon="material-symbols:favorite-rounded" />
    </RouterLink>
  </nav>
  <div class="container page">
    <h1 class="title">Recommended for you</h1>
    <div class="recs-grid">
      <RecommendationCard
        v-for="rec in recommendations"
        :recId="props.id"
        :key="rec.boardgame.id"
        :recommendation="rec"
        :explanationStyle="rec.explanation.type"
        size="large"
        @viewgame="viewgame"
      />
    </div>
  </div>
  <div class="floating-footer">
    <RouterLink :to="'/explore/' + props.id" class="floating-button btn-primary"
      >Change Preferences</RouterLink
    >
  </div>
</template>

<style scoped>
.floating-footer {
  position: fixed;
  background-color: var(--color-surface);
  border-top: 1px solid var(--color-border);
  bottom: 0;
  left: 0;
  width: 100%;
  box-shadow: var(--shadow-1);
}

.floating-button {
  display: block;
  width: fit-content;
  margin: var(--space-3) auto;
  text-align: center;
  font-size: var(--text-md);
  text-decoration: none;
}

.page {
  padding-bottom: 72px;
}
.title {
  font-size: var(--text-xl);
  margin: var(--space-3) var(--space-2);
  font-weight: 700;
}
.recs-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-3);
}
</style>
