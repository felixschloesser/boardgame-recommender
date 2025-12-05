<script lang="ts" setup>
import RecommendationCard from '@/components/RecommendationCard.vue'
import type { Recommendation } from '@/recommendation.mjs'
import { ref } from 'vue'

interface Props {
  explanationStyle: 'analogy' | 'feature'
}

const props = defineProps<Props>()

import { getWishlist } from '@/wishlist.mjs'

const recommendations = ref<Recommendation[]>(getWishlist())
</script>

<template>
  <nav class="navbar">
    <RouterLink to="/"><img src="../assets/home.svg" alt="Home" class="icon" /></RouterLink>
  </nav>
  <h1>Wishlist</h1>
  <div>
    <div v-if="recommendations.length === 0">
      <p>Your wishlist is currently empty. Find games in the Explore page</p>
    </div>
    <div class="wishlist-grid" v-else>
      <RecommendationCard
        v-for="rec in recommendations"
        :key="rec.boardgame.id"
        :recommendation="rec"
        size="small"
        :explanation-style="props.explanationStyle"
      ></RecommendationCard>
    </div>
  </div>
</template>

<style scoped>
.wishlist-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}
</style>
