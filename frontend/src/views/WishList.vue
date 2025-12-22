<script lang="ts" setup>
import RecommendationCard from '@/components/RecommendationCard.vue'
import type { Recommendation } from '@/recommendation.mjs'
import { useWishlistStore } from '@/stores/wishlist'
import { ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

const router = useRouter()
const wishlist = useWishlistStore()

const participant_id = localStorage.getItem('participant_id')
const recommendations = ref<Recommendation[]>(wishlist.recommendationsFor(participant_id ?? ''))
const taskCompleted = wishlist.hasCompletedTask(participant_id ?? '')

const viewgame = (rec: Recommendation) => {
  router.push(`/game/${rec.id ?? ''}/${rec.boardgame.id}`)
}

const openQuestionnaire = () => {
  const session_type = localStorage.getItem('session_type')
  const link_to_questionnaire = `https://forms.office.com/Pages/ResponsePage.aspx?id=m1hzOUCetU6ADrC2OD0WIWDTpTeScE9JrBYStf8YoldUQ01BRjBMWUpKRVVTTTdFT1dLVTc5MFo0WS4u&r012cbe1c0c8e4f43a3d2ba264e1062c4=${participant_id}&r3529d9540eb242369503b3859521d1d6="Session%20type%20${session_type}"`
  window.open(link_to_questionnaire, '_blank')
}
</script>

<template>
  <nav class="navbar">
    <RouterLink to="/"><Icon class="icon-btn" icon="material-symbols:home-rounded" /></RouterLink>
  </nav>
  <h1 class="title">Wishlist</h1>
  <div v-if="taskCompleted" class="task-completed">
    <p class="empty">
      You have completed your wishlist task. Please fill in the questionnaire by clicking this
      button
    </p>
    <button class="btn-primary" @click="openQuestionnaire">Go to Questionnaire</button>
  </div>
  <div class="container">
    <div v-if="recommendations.length === 0">
      <p class="empty">Your wishlist is currently empty. Find games in the Explore page</p>
    </div>
    <div class="wishlist-grid" v-else>
      <RecommendationCard
        v-for="rec in recommendations"
        :recId="rec.id ?? ''"
        :key="rec.boardgame.id"
        :recommendation="rec"
        :participant_id="participant_id ?? ''"
        size="small"
        :explanation-style="rec.explanation.type"
        @viewgame="viewgame(rec)"
      ></RecommendationCard>
    </div>
  </div>
</template>

<style scoped>
.task-completed {
  margin: var(--space-4);
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background-color: var(--color-bg-secondary);
  text-align: center;
}

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
