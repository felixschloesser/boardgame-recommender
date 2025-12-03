<script lang="ts" setup>
import type { Recommendation } from '../recommendation.mjs'

interface Props {
  recommendation: Recommendation
  explanationStyle: 'analogy' | 'feature'
}

const props = defineProps<Props>()
</script>

<template>
  <div class="recommendation-card">
    <div style="padding: 8px">
      <div class="game-image">
        <img :src="props.recommendation.boardgame.image_url" alt="Game image" />
      </div>
    </div>
    <div>
      <div class="game-title">
        <h2>{{ props.recommendation.boardgame.title }}</h2>
        <div class="wishlist-button">
          <button>{{ '<3' }}</button>
        </div>
      </div>
      <div class="explanation">
        <div v-if="props.explanationStyle === 'feature'">
          <div
            class="explanation-tab"
            v-for="feature in props.recommendation.explanation.features"
            :key="feature"
          >
            {{ feature }}
          </div>
        </div>
        <div v-else-if="props.explanationStyle === 'analogy'">
          <div
            class="explanation-tab"
            v-for="reference in props.recommendation.explanation.references"
            :key="reference"
          >
            {{ reference }}
          </div>
        </div>
      </div>
      <div class="redirect-arrow">
        <button>{{ '→' }}</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.recommendation-card {
  border: 2px solid #000;
  border-radius: 8px;
  display: flex;
  flex-direction: row;
  width: 350px;
  padding: 16px;
  max-width: 400px;
  margin: 16px auto;
  box-shadow: 2px 2px 12px rgba(0, 0, 0, 0.1);
}

.game-title {
  display: flex;
  justify-content: space-between;
  width: 180px;
  align-items: center;
}

.redirect-arrow {
  display: flex;
  justify-content: flex-end;
  width: 100%;
}

.explanation-tab {
  background-color: #a2a6d0;
  border: 1px solid #002bd5;
  border-radius: 4px;
  padding: 3px 6px;
  margin: 4px;
}

.explanation {
  display: flex;
  flex-wrap: wrap;
  align-items: flex;
}

.game-image img {
  width: 150px;
  height: 150px;
}
</style>
