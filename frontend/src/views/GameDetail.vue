<script lang="ts" setup>
import type BoardGame from '@/boardGame.mjs'
import type { Recommendation } from '@/recommendation.mjs'
import { ref } from 'vue'

interface Props {
  id: string // rec_id is required from the route
  explanationStyle: 'analogy' | 'feature'
}

const exampleRecommendation = {
  boardgame: {
    id: '161527',
    title: 'Catan: Ancient Egypt',
    description: '',
    mechanics: ['dice rolling negotiation network and route building trading'],
    genre: ['family'],
    themes: ['civilization'],
    min_players: 3,
    max_players: 4,
    complexity: 0.7109773918109924,
    age_recommendation: 0,
    num_user_ratings: 0,
    avg_user_rating: 7.26921,
    year_published: 0,
    playing_time_minutes: 75,
    image_url:
      'https://cf.geekdo-images.com/0XODRpReiZBFUffEcqT5-Q__imagepage/img/enC7UTvCAnb6j1Uazvh0OBQjvxw=/fit-in/900x600/filters:no_upscale():strip_icc()/pic9156909.png',
    bgg_url: 'https://boardgamegeek.com/boardgame/161527',
  },
  explanation: {
    references: ['Uno', 'Monopoly'],
    features: ['Trading', 'Building'],
  },
}

const props = defineProps<Props>()

//todo fetch recommendation from backend using props.id
const recommendation = ref<Recommendation | undefined>(exampleRecommendation)
const game = ref<BoardGame | undefined>(exampleRecommendation.boardgame)

const addToWishList = () => {
  //todo add recommendation to wishlist
}
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
          <div class="wishlist-button">
            <button @click="addToWishList">{{ '<3' }}</button>
          </div>
        </div>
        <div class="explanation">
          <div v-if="props.explanationStyle === 'feature'">
            <div
              class="explanation-tab"
              v-for="feature in recommendation?.explanation.features"
              :key="feature"
            >
              {{ feature }}
            </div>
          </div>
          <div v-else-if="props.explanationStyle === 'analogy'">
            <div
              class="explanation-tab"
              v-for="reference in recommendation?.explanation.references"
              :key="reference"
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
