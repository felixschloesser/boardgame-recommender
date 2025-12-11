<script lang="ts" setup>
import type BoardGame from '@/boardGame.mjs'
import type { Recommendation } from '@/recommendation.mjs'
import * as api from '@/api.mjs'
import { onMounted, ref } from 'vue'
import { addRecommendationToWishlist, inWishlist, removeRecommendationFromWishlist } from '@/wishlist.mts'

interface Props {
  id: string // rec_id is required from the route
  explanationStyle: 'references' | 'features'
  gameId: string
}

const props = defineProps<Props>()

//todo fetch recommendation from backend using props.id
const recommendation = ref<Recommendation | undefined>(undefined)
const game = ref<BoardGame | undefined>(undefined)
const isInWishlist = ref(false)

const toggleWishList = () => {
  if (inWishlist(recommendation.value!)) {
    // Already in wishlist, do nothing for 
    removeRecommendationFromWishlist(recommendation.value!)
    isInWishlist.value = false
    return
  } else {
    isInWishlist.value = true
    addRecommendationToWishlist(recommendation.value!)
  }
}

onMounted(async () => {
  const response = await api.getSessionRecommendations(props.id)
  recommendation.value = response.find((rec) => rec.boardgame.id === props.gameId) as Recommendation
  if (recommendation.value) {
    game.value = recommendation.value.boardgame
    isInWishlist.value = inWishlist(recommendation.value)
  }
})

</script>

<template>
  <nav class="navbar">
    <a @click="$router.go(-1)"><img src="../assets/back_arrow.svg" alt="Back" class="icon" /></a>
  </nav>
  <div>
    <div class="recommendation-card">
      <div style="padding: 8px">
        <div class="game-image">
          <img :src="game?.image_url" alt="Game image" />
        </div>
      </div>
      <div>
        <div class="game-title">
          <h2>{{ game?.title }}</h2>
          <div @click="toggleWishList" class="wishlist-button">
            <img v-if="isInWishlist" src="../assets/filled_heart.svg" alt="In Wishlist" />
            <img v-else src="../assets/heart.svg" alt="Wishlist" />
          </div>
        </div>
        <div class="explanation">
          <div v-if="props.explanationStyle === 'features'">
            <div
              class="explanation-tab"
              v-for="feature in recommendation?.explanation.features"
              :key="feature.label"
            >
              {{ feature }}
            </div>
          </div>
          <div v-else-if="props.explanationStyle === 'references'">
            <div
              class="explanation-tab"
              v-for="reference in recommendation?.explanation.references"
              :key="reference.bgg_id"
            >
              {{ reference }}
            </div>
          </div>
        </div>
      </div>
    </div>
    <div class="info-tabs">
      <div class="info" v-for="genre in game?.genre" :key="genre">{{ genre }}</div>
      <div class="info" v-for="theme in game?.themes" :key="theme">{{ theme }}</div>
      <div class="info">BRAIN {{ game?.complexity.toPrecision(2) }}</div>
      <div class="info">{{ game?.min_players }}-{{ game?.max_players }} Players</div>
      <div class="info" v-if="(game?.age_recommendation ?? 0) > 0">
        AGE {{ game?.age_recommendation }}+
      </div>
      <div class="info">{{ game?.playing_time_minutes }} mins</div>
      <div class="info">STER {{ game?.avg_user_rating.toPrecision(2) }}</div>
    </div>
    <div class="overview">
      <h3>Overview:</h3>
      <p>{{ game?.description }}</p>
    </div>
  </div>
</template>

<style scoped>
.recommendation-card {
  display: flex;
  flex-direction: row;
  width: 350px;
  padding: 16px;
  max-width: 400px;
  margin: 16px auto;
}

.game-title {
  display: flex;
  justify-content: space-between;
  width: 180px;
  align-items: center;
}

.explanation-tab {
  background-color: #a2a6d0;
  border: 1px solid #002bd5;
  border-radius: 4px;
  padding: 3px 6px;
  margin: 4px;
}

.info-tabs {
  display: flex;
  flex-wrap: wrap;
  width: 350px;
  justify-content: left;
  margin: 16px 0;
}

.info {
  margin: 4px;
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
