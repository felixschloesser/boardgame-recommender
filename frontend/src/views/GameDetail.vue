<script lang="ts" setup>
import type BoardGame from '@/boardGame.mjs'
import type { Recommendation } from '@/recommendation.mjs'
import * as api from '@/api.mjs'
import { computed, onMounted, ref } from 'vue'
import {
  addRecommendationToWishlist,
  inWishlist,
  removeRecommendationFromWishlist,
} from '@/wishlist.mts'

interface Props {
  id: string // rec_id is required from the route
  explanationStyle: 'references' | 'features'
  gameId: string
}

const props = defineProps<Props>()

// Local chip types for explanations
interface FeatureChip {
  label: string
  influence?: string | number
}
interface ReferenceChip {
  bgg_id: string
  title: string
  influence?: string | number
}

// fetch recommendation from backend using props.id
const recommendation = ref<Recommendation | undefined>(undefined)
const game = ref<BoardGame | undefined>(undefined)
const isInWishlist = ref(false)

const toggleWishList = () => {
  if (recommendation.value && inWishlist(recommendation.value)) {
    removeRecommendationFromWishlist(recommendation.value)
    isInWishlist.value = false
    return
  } else if (recommendation.value) {
    isInWishlist.value = true
    addRecommendationToWishlist(recommendation.value)
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

// Normalize influence to 'positive' | 'neutral' | 'negative'
const normInfluence = (val: unknown): 'positive' | 'neutral' | 'negative' => {
  if (typeof val === 'string') {
    const v = val.toLowerCase()
    if (v.includes('pos') || v === '+') return 'positive'
    if (v.includes('neg') || v === '-') return 'negative'
    return 'neutral'
  }
  if (typeof val === 'number') {
    if (val > 0) return 'positive'
    if (val < 0) return 'negative'
    return 'neutral'
  }
  return 'neutral'
}

// Collapse long explanations so the card doesn't grow too tall
const expanded = ref(false)
const maxChips = 8

const featureChips = computed<FeatureChip[]>(() => {
  const items = (recommendation.value?.explanation?.features as FeatureChip[]) || []
  return expanded.value ? items : items.slice(0, maxChips)
})

const referenceChips = computed<ReferenceChip[]>(() => {
  const items = (recommendation.value?.explanation?.references as unknown as ReferenceChip[]) || []
  return expanded.value ? items : items.slice(0, maxChips)
})
</script>

<template>
  <nav class="navbar">
    <a @click="$router.go(-1)"
      ><Icon class="icon-btn" icon="material-symbols:arrow-back-rounded"
    /></a>
  </nav>
  <div class="container">
    <div class="detail-card card">
      <div class="media">
        <div class="game-image thumb">
          <img :src="game?.image_url" alt="Game image" />
        </div>
      </div>
      <div class="content">
        <div class="game-title">
          <h2 class="title">{{ game?.title }}</h2>
          <button @click="toggleWishList" class="wishlist-button btn-outline" :aria-pressed="isInWishlist">
            <Icon
              v-if="isInWishlist"
              icon="material-symbols:favorite-rounded"
              style="color: var(--color-danger)"
              width="22"
              height="22"
            />
            <Icon v-else icon="material-symbols:favorite-outline-rounded" width="22" height="22" />
          </button>
        </div>

        <div class="explanations" v-if="recommendation">
          <template v-if="props.explanationStyle === 'features'">
            <div
              v-for="feature in featureChips"
              :key="feature.label"
              :class="`explanation-chip explanation-${normInfluence(feature.influence)} chip`"
            >
              {{ feature.label }}
            </div>
          </template>
          <template v-else-if="props.explanationStyle === 'references'">
            <div
              v-for="reference in referenceChips"
              :key="reference.bgg_id"
              :class="`explanation-chip explanation-${normInfluence(reference.influence)} chip`"
            >
              {{ reference.title }}
            </div>
          </template>
          <button
            v-if="
              (props.explanationStyle === 'features' &&
                (recommendation?.explanation?.features?.length || 0) > maxChips) ||
              (props.explanationStyle === 'references' &&
                (recommendation?.explanation?.references?.length || 0) > maxChips)
            "
            class="toggle-explanations"
            type="button"
            @click="expanded = !expanded"
          >
            {{ expanded ? 'Show less' : 'Show more' }}
          </button>
        </div>
      </div>
    </div>

    <div class="info-tabs">
      <div class="info chip" v-for="genre in game?.genre" :key="genre">{{ genre }}</div>
      <div class="info chip" v-for="theme in game?.themes" :key="theme">{{ theme }}</div>
      <div class="info chip" v-if="game">BRAIN {{ game?.complexity?.toPrecision(2) }}</div>
      <div class="info chip">{{ game?.min_players }}-{{ game?.max_players }} Players</div>
      <div class="info chip" v-if="(game?.age_recommendation ?? 0) > 0">
        AGE {{ game?.age_recommendation }}+
      </div>
      <div class="info chip">{{ game?.playing_time_minutes }} mins</div>
      <div class="info chip" v-if="game">STER {{ game?.avg_user_rating?.toPrecision(2) }}</div>
    </div>

    <div class="overview card">
      <h3 class="overview-title">Overview</h3>
      <p class="overview-text">{{ game?.description }}</p>
    </div>
  </div>
</template>

<style scoped>
.detail-card {
  display: flex;
  flex-direction: row;
  width: 100%;
  padding: var(--space-4);
  margin: var(--space-4) 0;
  gap: var(--space-4);
  box-sizing: border-box;
}

.game-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-2);
}

.title {
  font-size: var(--text-lg);
  margin: 0;
}

.info-tabs {
  display: flex;
  flex-wrap: wrap;
  width: 100%;
  justify-content: flex-start;
  margin: var(--space-4) 0;
}

.info {
  /* chip base class added in template */
}

.explanations {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: var(--space-1);
}

.explanation-chip { margin: 4px; }

.media {
  flex: 0 0 auto;
}
.game-image {
  width: 148px;
  height: 148px;
}

.content {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.wishlist-button {
  cursor: pointer;
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.overview {
  padding: var(--space-4);
  margin-bottom: var(--space-5);
}
.overview-title {
  margin: 0 0 var(--space-2);
  font-size: var(--text-lg);
}
.overview-text {
  margin: 0;
  color: var(--color-text);
}

/* Responsive adjustments for narrow screens */
@media (max-width: 520px) {
  .detail-card {
    flex-direction: column;
    padding: var(--space-3);
    gap: var(--space-3);
  }
  .media {
    width: 100%;
  }
  .game-image {
    width: 100%;
    height: 180px;
  }
}
</style>
