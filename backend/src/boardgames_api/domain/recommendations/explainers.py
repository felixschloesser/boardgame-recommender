from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from boardgames_api.domain.games.service import get_boardgame
from boardgames_api.domain.recommendations.context import RecommendationContext, ScoredCandidate
from boardgames_api.domain.recommendations.schemas import (
    FeatureExplanation,
    RecommendationExplanation,
    ReferenceExplanation,
)
from boardgames_api.domain.recommendations.scoring import EmbeddingScorer
from boardgames_api.http.dependencies import db_session

_MECHANICS_LIST = ["acting", "action event", "action drafting", "action points",
 "action queue", "action retrieval", "action timer", "advantage token", "alliances", 
 "area majority influence", "area movement", "area impulse", "auction bidding", "auction compensation", 
 "auction: dexterity", "auction: dutch", "auction: dutch priority", "auction: english", 
 "auction: fixed placement", "auction: multiple lot", "auction: once around", "auction: sealed bid", 
 "auction: turn order until pass", "automatic resource growth", "betting and bluffing", "bias", 
 "bids as wagers", "bingo", "bribery", "campaign battle card driven", "card play conflict resolution", 
 "catch the leader", "chaining", "chit pull system", "closed drafting", "closed economy auction", 
 "command cards", "commodity speculation", "communication limits", "connections", "constrained bidding", 
 "contracts", "cooperative game", "crayon rail system", "critical hits and failures", "cube tower", 
 "deck construction", "deck bag and pool building", "deduction", "delayed purchase", "dice rolling", 
 "die icon resolution", "different dice movement", "drawing", "elapsed real time ending", "enclosure", 
 "end game bonuses", "events", "finale ending", "flicking", "follow", "force commitment", "grid coverage", 
 "grid movement", "hand management", "hexagon grid", "hidden movement", "hidden roles", "hidden victory points", 
 "highest lowest scoring", "hot potato", "i cut you choose", "impulse movement", "income", 
 "increase value of unchosen resources", "induction", "interrupts", "investment", "kill steal", 
 "king of the hill", "ladder climbing", "layering", "legacy game", "line drawing", "line of sight", 
 "loans", "lose a turn", "mancala", "map addition", "map deformation", "map reduction", "market", 
 "matching", "measurement movement", "melding and splaying", "memory", "minimap resolution", 
 "modular board", "move through deck", "movement points", "movement template", "moving multiple units", 
 "multi use cards", "multiple maps", "narrative choice paragraph", "negotiation", "neighbor scope", 
 "network and route building", "once per game abilities", "open drafting", "order counters", "ordering", 
 "ownership", "paper and pencil", "passed action token", "pattern building", "pattern movement", 
 "pattern recognition", "physical removal", "pick up and deliver", "pieces as map", "player elimination", 
 "player judge", "point to point movement", "predictive bid", "prisoner's dilemma", "programmed movement", 
 "push your luck", "questions and answers", "race", "random production", "ratio combat results table", 
 "re rolling and locking", "real time", "relative movement", "resource queue", "resource to move", 
 "rock paper scissors", "role playing", "roles with asymmetric information", "roll spin and move", "rondel", 
 "scenario mission campaign game", "score and reset game", "secret unit deployment", "selection order bid", 
 "semi cooperative game", "set collection", "simulation", "simultaneous action selection", "singing", 
 "single loser game", "slide push", "solo solitaire game", "speed matching", "spelling", "square grid", 
 "stacking and balancing", "stat check resolution", "static capture", "stock holding", "storytelling", 
 "sudden death ending", "tags", "take that", "targeted clues", "team based game", "tech trees tech tracks", 
 "three dimensional movement", "tile placement", "track movement", "trading", "traitor game", "trick taking", 
 "tug of war", "turn order: auction", "turn order: claim action", "turn order: pass order", 
 "turn order: progressive", "turn order: random", "turn order: role order", "turn order: stat based", 
 "turn order: time track", "variable phase order", "variable player powers", "variable set up", 
 "victory points as a resource", "voting", "worker placement", "worker placement with dice workers", 
 "worker placement different worker types", "zone of control"]

_THEME_LIST = ["abstract strategy", "action dexterity", "adventure", "age of reason", "american civil war", 
               "american indian wars", "american revolutionary war", "american west", "ancient", "animals", 
               "arabian", "aviation flight", "bluffing", "book", "card game", "children's game", "city building", 
               "civil war", "civilization", "collectible components", "comic book strip", "deduction", "dice", 
               "economic", "educational", "electronic", "environmental", "expansion for base game", "exploration", 
               "fan expansion", "fantasy", "farming", "fighting", "game system", "horror", "humor", "industry manufacturing", 
               "korean war", "mafia", "math", "mature adult", "maze", "medical", "medieval", "memory", "miniatures", 
               "modern warfare", "movies tv radio theme", "murder mystery", "music", "mythology", "napoleonic", 
               "nautical", "negotiation", "novel based", "number", "party game", "pike and shot", "pirates", "political", 
               "post napoleonic", "prehistoric", "print & play", "puzzle", "racing", "real time", "religious", 
               "renaissance", "science fiction", "space exploration", "spies secret agents", "sports", "territory building", 
               "third party expansion", "trains", "transportation", "travel", "trivia", "video game theme", "vietnam war", 
               "wargame", "word game", "world war i", "world war ii", "zombies"]

_GENRE_LIST = ["abstract", "card", "childrens", "customizable", "family", "party", "strategy", "thematic", "war"]

class SimilarityExplanationProvider:
    """
    Reference-based explanations using the embedding index.
    """

    def __init__(self, max_references: int = 3) -> None:
        self.max_references = max_references

    def explain(
        self, context: RecommendationContext, scored: List[ScoredCandidate], db: Session
    ) -> List[RecommendationExplanation]:
        store = context.embedding_index
        liked_ids = [int(liked) for liked in context.liked_games if store.has_id(int(liked))]
        explanations: List[RecommendationExplanation] = []
        scorer = EmbeddingScorer()
        for item in scored:
            
            explanations_scored_sorted: List[ScoredCandidate] = []
            refs: List[ReferenceExplanation] = []
            for liked_id in liked_ids:

                id_object = type('',(),{})()
                id_object.id = liked_id

                liked_game_response = get_boardgame(liked_id,db)
                
                explanation_context = RecommendationContext(
                    liked_games=[item.candidate.id],
                    play_context=context.play_context,
                    num_results=1,
                    candidates=[liked_game_response],
                    participant_id=context.participant_id,
                    study_group=context.study_group,
                    embedding_index=context.embedding_index,
                )

                explanation_scored = scorer.score(explanation_context)
                explanations_scored_sorted.append(explanation_scored[0])

            def score_sort(
                    exp:ScoredCandidate
            ) :
                return exp.score
                               
            explanations_scored_sorted.sort(reverse=True, key=score_sort)

            for exp in explanations_scored_sorted:

                influence = ""
                if exp.score < 0.33:
                    influence = "negative"
                elif exp.score < 0.66:
                    influence = "neutral"
                else:
                    influence = "positive"

                refs.append(
                    ReferenceExplanation(
                        bgg_id=int(exp.candidate.id),
                        title=store.get_name(int(exp.candidate.id)) or "",
                        influence=influence,
                    )
                )
            explanations.append(
                RecommendationExplanation(
                    type="references",
                    references=refs,
                    features=None,
                )
            )
        return explanations


class FeatureHintExplanationProvider:
    """
    Lightweight feature-based explanations using existing metadata.
    Provides deterministic hints without introducing a SHAP dependency.
    This is deliberately a placeholder: it always marks surfaced hints as
    positively influential and does not compute real contributions.
    """

    def __init__(self, max_features: int = 3) -> None:
        self.max_features = max_features

    def explain(
        self, context: RecommendationContext, scored: List[ScoredCandidate], db: Session
    ) -> List[RecommendationExplanation]:
        explanations: List[RecommendationExplanation] = []
        scorer = EmbeddingScorer()
        for item in scored:

            #Collect all features from liked games that contributed to the recommendation
            relevant_features_collection : List[tuple[str, str]]= []
            liked_ids=context.liked_games
            for liked_id in liked_ids:

                liked_game_response = get_boardgame(liked_id,db)               
                
                explanation_context = RecommendationContext(
                    liked_games=[item.candidate.id],
                    play_context=context.play_context,
                    num_results=1,
                    candidates=[liked_game_response],
                    participant_id=context.participant_id,
                    study_group=context.study_group,
                    embedding_index=context.embedding_index,
                )
                explanation_scored = scorer.score(explanation_context)
                if explanation_scored[0].score >= 0.5:
                    relevant_features_collection.extend(self._feature_hints(explanation_scored[0]))
            

            hints: List[FeatureExplanation] = []
            for label, category in self._feature_hints(item):

                complete_labels = []
                searchList = []
                if category == "mechanic":
                    searchList = _MECHANICS_LIST
                elif category == "theme":
                    searchList = _THEME_LIST
                else:
                    searchList = _GENRE_LIST

                split_labels = label.split()
                index = 0
                while index < len(split_labels):
                    
                    def check_occurance(
                            optionList: List[str], searchList: List[str], startindex: int, currentindex: int
                    ) -> int:
                       searchList_string = "/".join(searchList)
                       searchword = " ".join(optionList[startindex:currentindex+1])
                       searchword_plus_one = " ".join(optionList[startindex:currentindex+2])
                       if ((searchword in searchList_string) and (searchword_plus_one not in searchList_string)) or (searchword == searchword_plus_one):
                           return currentindex+1
                       else:
                           return check_occurance(optionList,searchList,startindex,currentindex+1)
                       
                    if category == "genre":
                        if split_labels[index] in searchList:
                            complete_labels.append(split_labels[index])
                        index += 1
                    else:            
                        split_index = check_occurance(split_labels,searchList,index,index)
                        complete_label = " ".join(split_labels[index:split_index])
                        complete_labels.append(complete_label)
                        index = split_index        
                
                relevant_tuple: tuple[str,str]
                for tuple_item in relevant_features_collection:
                    if tuple_item[1] == category:
                        relevant_tuple = tuple_item

                for full_label in complete_labels:
                    if category == relevant_tuple[1] and full_label in relevant_tuple[0]:
                        hints.insert(0,
                            FeatureExplanation(
                                label = full_label,
                                category = category,
                                influence = "positive",
                            )
                        )
                    else:
                        hints.append(
                            FeatureExplanation(
                                label = full_label,
                                category = category,
                                influence = "negative",
                            )
                        )
                    if len(hints) >= self.max_features:
                        break

            explanations.append(
                RecommendationExplanation(
                    type="features",
                    features=hints,
                    references=None,
                )
            )
        return explanations

    def _feature_hints(self, item: ScoredCandidate) -> List[tuple[str, str]]:
        game = item.candidate
        suggestions: List[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()

        def _add(label: str, category: str) -> None:
            key = (label, category)
            if label and key not in seen:
                seen.add(key)
                suggestions.append(key)

        for mechanic in game.mechanics or []:
            _add(mechanic, "mechanic")
        for theme in game.themes or []:
            _add(theme, "theme")
        for genre in game.genre or []:
            _add(genre, "genre")
        if not suggestions:
            _add(game.title, "theme")
        return suggestions
