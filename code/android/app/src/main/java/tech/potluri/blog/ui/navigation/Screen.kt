package tech.potluri.blog.ui.navigation

sealed class Screen(val route: String) {
    object Feed : Screen("feed")
    object Detail : Screen("detail/{postId}") {
        fun createRoute(postId: String) = "detail/$postId"
    }
    object Author : Screen("author")
    object Admin : Screen("admin")
}
