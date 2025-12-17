<script lang="ts" setup>
import RecommendationCard from '@/components/RecommendationCard.vue'
import type { Recommendation } from '@/recommendation.mjs'
import { ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { getWishlist, getRecommendationsForId } from '@/wishlist.mjs'

const router = useRouter()

const reccommendationId = ref(getWishlist().keys().next().value || '')
const recommendations = ref<Recommendation[]>(getRecommendationsForId(reccommendationId.value))

const viewgame = (gameId: number) => {
  router.push(`/game/${reccommendationId.value}/${gameId}`)
}
</script>

<template>
  <nav class="navbar">
    <RouterLink to="/"><Icon class="icon-btn" icon="material-symbols:home-rounded" /></RouterLink>
  </nav>
  <h1 class="title">Wishlist</h1>
  <div class="container">
    <div v-if="recommendations.length === 0">
      <p class="empty">Your wishlist is currently empty. Find games in the Explore page</p>
    </div>
    <div class="wishlist-grid" v-else>
      <RecommendationCard
        v-for="rec in recommendations"
        :recId="reccommendationId"
        :key="rec.boardgame.id"
        :recommendation="rec"
        size="small"
        :explanation-style="rec.explanation.type"
        @viewgame="viewgame"
      ></RecommendationCard>
    </div>
  </div>
</template>

<style scoped>
.title {
  font-size: var(--text-xl);
  margin: var(--space-3) var(--space-2);
}
.empty {
  color: var(--color-text-muted);
  text-align: center;
}
.wishlist-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-3);
}

@media (min-width: 480px) {
  .wishlist-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (min-width: 768px) {
  .wishlist-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}
</style>
