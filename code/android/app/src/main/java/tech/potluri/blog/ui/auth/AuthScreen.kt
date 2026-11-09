package tech.potluri.blog.ui.auth

import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import android.net.Uri
import android.provider.OpenableColumns
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.AdminPanelSettings
import androidx.compose.material.icons.filled.Article
import androidx.compose.material.icons.filled.AttachFile
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Code
import androidx.compose.material.icons.filled.DynamicFeed
import androidx.compose.material.icons.filled.Key
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.PostAdd
import androidx.compose.material.icons.filled.RssFeed
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material.icons.filled.Widgets
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SuggestionChip
import androidx.compose.material3.SuggestionChipDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.Modifier
import androidx.compose.ui.autofill.AutofillNode
import androidx.compose.ui.autofill.AutofillType
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.layout.boundsInWindow
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.LocalAutofill
import androidx.compose.ui.platform.LocalAutofillTree
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.credentials.CreatePasswordRequest
import androidx.credentials.CredentialManager
import androidx.credentials.GetCredentialRequest
import androidx.credentials.GetPasswordOption
import androidx.credentials.PasswordCredential
import androidx.credentials.exceptions.CreateCredentialException
import androidx.credentials.exceptions.GetCredentialException
import androidx.lifecycle.viewmodel.compose.viewModel
import coil.compose.AsyncImage
import kotlinx.coroutines.launch
import tech.potluri.blog.BuildConfig
import tech.potluri.blog.data.model.Post

private tailrec fun Context.findActivity(): Activity? = when (this) {
    is Activity -> this
    is ContextWrapper -> baseContext.findActivity()
    else -> null
}

// 14 Rich Text Block Snippets matching static/js/blocks.js and templates/_rich_blocks_menu.html
val RICH_TEXT_BLOCKS = listOf(
    Pair("Heading", "# Section heading"),
    Pair("Quote", ":::quote\nQuoted text\n:::"),
    Pair("Callout", ":::callout{type=info}\nSomething worth noting.\n:::"),
    Pair("Link preview", ":::link https://example.com\nShort description (optional)\n:::"),
    Pair("Table", ":::table\n| Header A | Header B |\n| --- | --- |\n| Cell 1 | Cell 2 |\n:::"),
    Pair("Poll", ":::poll\nYour question?\n- Option one\n- Option two\n:::"),
    Pair("Gallery", ":::gallery\nhttps://example.com/image-1.jpg\nhttps://example.com/image-2.jpg\n:::"),
    Pair("Toggle", ":::toggle Click to expand\nHidden content goes here.\n:::"),
    Pair("Button / CTA", ":::cta https://example.com\nButton label\n:::"),
    Pair("Embed", ":::embed https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
    Pair("Math (LaTeX)", ":::math\nE = mc^2\n:::"),
    Pair("Footnote", "[^1]\n\n[^1]: Footnote text"),
    Pair("Divider", ":::divider"),
    Pair("Table of contents", ":::toc")
)

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class, ExperimentalComposeUiApi::class)
@Composable
fun AuthScreen(
    onSignedIn: () -> Unit = {},
    onNavigateToFeed: () -> Unit = {},
    onPublished: () -> Unit = {},
    viewModel: AuthViewModel = viewModel()
) {
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()
    val credentialManager = remember { CredentialManager.create(context) }

    val state by viewModel.uiState.collectAsState()
    var username by rememberSaveable { mutableStateOf("") }
    var password by rememberSaveable { mutableStateOf("") }
    var passwordVisible by rememberSaveable { mutableStateOf(false) }
    var pendingPasswordToSave by remember { mutableStateOf<Pair<String, String>?>(null) }
    var savedVaultAccounts by remember { mutableStateOf(CredentialVault.getSavedCredentials(context)) }
    var showSavedCredentialsDialog by remember { mutableStateOf(false) }

    val postContent = state.draftContent
    val postTags = state.draftTags

    // Dialog & Sheet states
    var showArticlePicker by remember { mutableStateOf(false) }
    var showBlocksSheet by remember { mutableStateOf(false) }
    var showPostPicker by remember { mutableStateOf(false) }

    val blocksSheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)

    // Refresh vault accounts whenever user logs out / returns to unauthenticated state
    LaunchedEffect(state.user) {
        if (state.user == null) {
            val accounts = CredentialVault.getSavedCredentials(context)
            savedVaultAccounts = accounts
            if (username.isBlank() && password.isBlank() && accounts.size == 1) {
                username = accounts.first().username
                password = accounts.first().password
            }
        }
    }

    // File picker launcher for all supported attachment types
    val filePickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenMultipleDocuments()
    ) { uris: List<Uri> ->
        uris.forEach { uri ->
            try {
                var fileName = "attachment"
                context.contentResolver.query(uri, null, null, null, null)?.use { cursor ->
                    val nameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                    if (nameIndex != -1 && cursor.moveToFirst()) {
                        fileName = cursor.getString(nameIndex)
                    }
                }
                val mimeType = context.contentResolver.getType(uri) ?: "application/octet-stream"
                val bytes = context.contentResolver.openInputStream(uri)?.use { it.readBytes() }
                if (bytes != null) {
                    viewModel.uploadMediaFile(fileName, mimeType, bytes)
                }
            } catch (e: Exception) {
                Toast.makeText(context, "Failed to read file: ${e.localizedMessage}", Toast.LENGTH_SHORT).show()
            }
        }
    }

    // Google Password Manager + Encrypted Vault: Save password after successful login
    LaunchedEffect(state.loginSucceeded) {
        if (state.loginSucceeded) {
            val creds = pendingPasswordToSave ?: Pair(username.trim(), password)
            if (creds.first.isNotBlank() && creds.second.isNotBlank() && !creds.first.equals("demo", ignoreCase = true)) {
                // 1. Always persist to hardware-backed EncryptedSharedPreferences vault so it is immediately available
                CredentialVault.saveCredential(context, creds.first, creds.second)
                savedVaultAccounts = CredentialVault.getSavedCredentials(context)

                // 2. Also prompt Google Password Manager via Android CredentialManager
                val activity = context.findActivity()
                if (activity != null) {
                    try {
                        val saveRequest = CreatePasswordRequest(id = creds.first, password = creds.second)
                        credentialManager.createCredential(activity, saveRequest)
                    } catch (e: CreateCredentialException) {
                        // User dismissed or Google Play Services deferred to EncryptedVault
                    } catch (e: Exception) {
                        // Ignore unexpected provider errors
                    }
                }
            }
            pendingPasswordToSave = null
            viewModel.consumeLoginSuccess()
            onSignedIn()
        }
    }

    Scaffold(
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        if (state.user != null) "Publisher Studio" else "Admin Access",
                        fontWeight = FontWeight.SemiBold
                    )
                },
                actions = {
                    Text(
                        text = "v${BuildConfig.VERSION_NAME}",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(end = 16.dp)
                    )
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface,
                    titleContentColor = MaterialTheme.colorScheme.onSurface
                )
            )
        }
    ) { paddingValues ->
        if (state.isLoading && state.user == null) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(paddingValues),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator(color = MaterialTheme.colorScheme.primary)
            }
            return@Scaffold
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.Top
        ) {
            val user = state.user
            if (user != null) {
                // --- Authenticated User Card ---
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)
                    ),
                    shape = RoundedCornerShape(16.dp)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(
                                    imageVector = if (user.is_admin) Icons.Default.AdminPanelSettings else Icons.Default.Person,
                                    contentDescription = null,
                                    tint = MaterialTheme.colorScheme.primary,
                                    modifier = Modifier.size(32.dp)
                                )
                                Spacer(Modifier.width(12.dp))
                                Column {
                                    Text(
                                        user.username,
                                        style = MaterialTheme.typography.titleMedium,
                                        fontWeight = FontWeight.Bold
                                    )
                                    SuggestionChip(
                                        onClick = {},
                                        label = {
                                            Text(
                                                if (user.is_admin) "Administrator" else "Demo Publisher",
                                                style = MaterialTheme.typography.labelSmall
                                            )
                                        },
                                        colors = SuggestionChipDefaults.suggestionChipColors(
                                            containerColor = if (user.is_admin)
                                                MaterialTheme.colorScheme.primaryContainer
                                            else
                                                MaterialTheme.colorScheme.secondaryContainer
                                        )
                                    )
                                }
                            }

                            OutlinedButton(
                                onClick = viewModel::logout,
                                enabled = !state.isLoading && !state.isPosting
                            ) {
                                Text("Sign out")
                            }
                        }

                        state.error?.let {
                            Spacer(Modifier.height(8.dp))
                            Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }

                Spacer(Modifier.height(20.dp))

                // --- Mobile Post Composer (No Article Creation) ---
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.surface
                    ),
                    elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
                    shape = RoundedCornerShape(16.dp)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text(
                            "New Post",
                            style = MaterialTheme.typography.titleLarge,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            "Publish directly to the blog feed from your mobile device.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )

                        Spacer(Modifier.height(16.dp))

                        // Content field
                        OutlinedTextField(
                            value = postContent,
                            onValueChange = { viewModel.updateDraftContent(it) },
                            label = { Text("Content (Markdown supported) *") },
                            placeholder = { Text("What would you like to share today?") },
                            minLines = 4,
                            maxLines = 10,
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(12.dp)
                        )

                        Spacer(Modifier.height(12.dp))

                        // --- Attachments Bar ---
                        Text(
                            "Attachments",
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = FontWeight.SemiBold,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Spacer(Modifier.height(6.dp))

                        FlowRow(
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                            verticalArrangement = Arrangement.spacedBy(8.dp),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            // 1. File Upload (all website MIME types)
                            FilterChip(
                                selected = false,
                                onClick = {
                                    filePickerLauncher.launch(
                                        arrayOf(
                                            "image/*",
                                            "video/*",
                                            "audio/*",
                                            "application/pdf",
                                            "application/msword",
                                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                            "application/vnd.ms-excel",
                                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                            "application/vnd.ms-powerpoint",
                                            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                                            "text/plain"
                                        )
                                    )
                                },
                                leadingIcon = {
                                    Icon(
                                        Icons.Default.AttachFile,
                                        contentDescription = null,
                                        tint = MaterialTheme.colorScheme.primary,
                                        modifier = Modifier.size(16.dp)
                                    )
                                },
                                label = { Text("Upload File") }
                            )

                            // 2. Attach Article (lists all articles)
                            FilterChip(
                                selected = false,
                                onClick = {
                                    viewModel.loadArticles()
                                    showArticlePicker = true
                                },
                                leadingIcon = {
                                    Icon(
                                        Icons.Default.Article,
                                        contentDescription = null,
                                        tint = MaterialTheme.colorScheme.primary,
                                        modifier = Modifier.size(16.dp)
                                    )
                                },
                                label = { Text("Attach Article") }
                            )

                            // 3. Attach Post
                            FilterChip(
                                selected = false,
                                onClick = { showPostPicker = true },
                                leadingIcon = {
                                    Icon(
                                        Icons.Default.DynamicFeed,
                                        contentDescription = null,
                                        tint = MaterialTheme.colorScheme.primary,
                                        modifier = Modifier.size(16.dp)
                                    )
                                },
                                label = { Text("Attach Post") }
                            )

                            // 4. Code Block
                            FilterChip(
                                selected = false,
                                onClick = { viewModel.appendSnippet("```\n\n```") },
                                leadingIcon = {
                                    Icon(
                                        Icons.Default.Code,
                                        contentDescription = null,
                                        tint = MaterialTheme.colorScheme.primary,
                                        modifier = Modifier.size(16.dp)
                                    )
                                },
                                label = { Text("Code") }
                            )

                            // 5. Rich-Text Block
                            FilterChip(
                                selected = false,
                                onClick = { showBlocksSheet = true },
                                leadingIcon = {
                                    Icon(
                                        Icons.Default.Widgets,
                                        contentDescription = null,
                                        tint = MaterialTheme.colorScheme.primary,
                                        modifier = Modifier.size(16.dp)
                                    )
                                },
                                label = { Text("Insert Block") }
                            )
                        }

                        // Uploading indicator or error
                        if (state.isUploadingMedia) {
                            Spacer(Modifier.height(8.dp))
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
                                Spacer(Modifier.width(8.dp))
                                Text("Uploading attachment...", style = MaterialTheme.typography.bodySmall)
                            }
                        }
                        state.uploadError?.let { err ->
                            Spacer(Modifier.height(6.dp))
                            Text(err, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                        }

                        // Attached media preview list
                        if (state.attachedMedia.isNotEmpty()) {
                            Spacer(Modifier.height(10.dp))
                            Column(
                                verticalArrangement = Arrangement.spacedBy(6.dp),
                                modifier = Modifier.fillMaxWidth()
                            ) {
                                state.attachedMedia.forEach { item ->
                                    Card(
                                        colors = CardDefaults.cardColors(
                                            containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)
                                        ),
                                        shape = RoundedCornerShape(8.dp),
                                        modifier = Modifier.fillMaxWidth()
                                    ) {
                                        Row(
                                            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                                            verticalAlignment = Alignment.CenterVertically,
                                            horizontalArrangement = Arrangement.SpaceBetween
                                        ) {
                                            Row(
                                                verticalAlignment = Alignment.CenterVertically,
                                                modifier = Modifier.weight(1f)
                                            ) {
                                                Icon(
                                                    Icons.Default.AttachFile,
                                                    contentDescription = null,
                                                    tint = MaterialTheme.colorScheme.primary,
                                                    modifier = Modifier.size(18.dp)
                                                )
                                                Spacer(Modifier.width(8.dp))
                                                Text(
                                                    text = item.name,
                                                    style = MaterialTheme.typography.bodySmall,
                                                    maxLines = 1,
                                                    overflow = TextOverflow.Ellipsis
                                                )
                                            }
                                            IconButton(
                                                onClick = { viewModel.removeAttachedMedia(item.url) },
                                                modifier = Modifier.size(24.dp)
                                            ) {
                                                Icon(
                                                    Icons.Default.Close,
                                                    contentDescription = "Remove",
                                                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                                                    modifier = Modifier.size(16.dp)
                                                )
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        Spacer(Modifier.height(16.dp))

                        // --- Syndication Platforms Checkboxes ---
                        if (state.syndicationPlatforms.isNotEmpty()) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(
                                    Icons.Default.Share,
                                    contentDescription = null,
                                    tint = MaterialTheme.colorScheme.primary,
                                    modifier = Modifier.size(18.dp)
                                )
                                Spacer(Modifier.width(8.dp))
                                Text(
                                    "Syndicate to (POSSE)",
                                    style = MaterialTheme.typography.labelLarge,
                                    fontWeight = FontWeight.SemiBold
                                )
                            }
                            Spacer(Modifier.height(6.dp))

                            FlowRow(
                                horizontalArrangement = Arrangement.spacedBy(6.dp),
                                verticalArrangement = Arrangement.spacedBy(4.dp),
                                modifier = Modifier.fillMaxWidth()
                            ) {
                                state.syndicationPlatforms.forEach { platform ->
                                    val isSelected = state.selectedPlatforms.contains(platform.id)
                                    val isAvailable = platform.configured || (user.is_demo)
                                    FilterChip(
                                        selected = isSelected,
                                        onClick = {
                                            if (isAvailable) {
                                                viewModel.togglePlatform(platform.id)
                                            } else {
                                                Toast.makeText(
                                                    context,
                                                    "${platform.label} is not configured on the server yet.",
                                                    Toast.LENGTH_SHORT
                                                ).show()
                                            }
                                        },
                                        enabled = isAvailable,
                                        leadingIcon = if (isSelected) {
                                            { Icon(Icons.Default.Check, contentDescription = null, modifier = Modifier.size(16.dp)) }
                                        } else null,
                                        label = {
                                            val limitText = platform.limit?.let { " (${it}ch)" } ?: ""
                                            Text("${platform.label}$limitText")
                                        }
                                    )
                                }
                            }

                            if (user.is_demo) {
                                Spacer(Modifier.height(4.dp))
                                Text(
                                    "Demo Mode: Simulated syndications will be applied.",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.secondary
                                )
                            }

                            Spacer(Modifier.height(14.dp))
                        }

                        // Tags field
                        OutlinedTextField(
                            value = postTags,
                            onValueChange = { viewModel.updateDraftTags(it) },
                            label = { Text("Tags (comma-separated)") },
                            placeholder = { Text("e.g. android, technology, life") },
                            singleLine = true,
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(12.dp),
                            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done)
                        )

                        Spacer(Modifier.height(16.dp))

                        // Success banner
                        if (state.postCreated) {
                            Card(
                                modifier = Modifier.fillMaxWidth(),
                                colors = CardDefaults.cardColors(
                                    containerColor = MaterialTheme.colorScheme.primaryContainer
                                ),
                                shape = RoundedCornerShape(12.dp)
                            ) {
                                Row(
                                    modifier = Modifier.padding(12.dp),
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Row(
                                        verticalAlignment = Alignment.CenterVertically,
                                        modifier = Modifier.weight(1f)
                                    ) {
                                        Icon(
                                            imageVector = Icons.Default.CheckCircle,
                                            contentDescription = null,
                                            tint = MaterialTheme.colorScheme.primary
                                        )
                                        Spacer(Modifier.width(8.dp))
                                        Text(
                                            "Post published successfully!",
                                            style = MaterialTheme.typography.bodyMedium,
                                            color = MaterialTheme.colorScheme.onPrimaryContainer,
                                            fontWeight = FontWeight.Medium
                                        )
                                    }
                                    Button(
                                        onClick = onNavigateToFeed,
                                        shape = RoundedCornerShape(8.dp)
                                    ) {
                                        Icon(Icons.Default.RssFeed, contentDescription = null, modifier = Modifier.size(16.dp))
                                        Spacer(Modifier.width(4.dp))
                                        Text("View Feed")
                                    }
                                }
                            }
                            Spacer(Modifier.height(16.dp))
                        }

                        // Error banner
                        state.postError?.let { err ->
                            Text(
                                err,
                                color = MaterialTheme.colorScheme.error,
                                style = MaterialTheme.typography.bodyMedium,
                                modifier = Modifier.padding(bottom = 12.dp)
                            )
                        }

                        // Action buttons
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(12.dp)
                        ) {
                            Button(
                                onClick = {
                                    val tagsList = postTags
                                        .split(",")
                                        .map { it.trim() }
                                        .filter { it.isNotEmpty() }
                                    viewModel.createPost(
                                        content = postContent,
                                        title = null,
                                        tags = tagsList,
                                        onCreated = onPublished
                                    )
                                },
                                enabled = !state.isPosting && (postContent.isNotBlank() || state.attachedMedia.isNotEmpty()),
                                modifier = Modifier.weight(1f),
                                shape = RoundedCornerShape(12.dp)
                            ) {
                                if (state.isPosting) {
                                    CircularProgressIndicator(
                                        modifier = Modifier.size(20.dp),
                                        color = MaterialTheme.colorScheme.onPrimary,
                                        strokeWidth = 2.dp
                                    )
                                    Spacer(Modifier.width(8.dp))
                                    Text("Publishing...")
                                } else {
                                    Icon(
                                        Icons.AutoMirrored.Filled.Send,
                                        contentDescription = null,
                                        modifier = Modifier.size(18.dp)
                                    )
                                    Spacer(Modifier.width(8.dp))
                                    Text("Publish")
                                }
                            }

                            OutlinedButton(
                                onClick = onNavigateToFeed,
                                shape = RoundedCornerShape(12.dp)
                            ) {
                                Text("Feed")
                            }
                        }
                    }
                }
            } else {
                // --- Unauthenticated Sign-in Card with Google Password Manager & Encrypted Vault ---
                val autofill = LocalAutofill.current
                val autofillTree = LocalAutofillTree.current
                val usernameAutofillNode = remember {
                    AutofillNode(
                        autofillTypes = listOf(AutofillType.Username, AutofillType.EmailAddress),
                        onFill = { username = it }
                    )
                }
                val passwordAutofillNode = remember {
                    AutofillNode(
                        autofillTypes = listOf(AutofillType.Password),
                        onFill = { password = it }
                    )
                }
                autofillTree += usernameAutofillNode
                autofillTree += passwordAutofillNode

                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.surface
                    ),
                    elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
                    shape = RoundedCornerShape(16.dp)
                ) {
                    Column(modifier = Modifier.padding(24.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(
                                imageVector = Icons.Default.Lock,
                                contentDescription = null,
                                tint = MaterialTheme.colorScheme.primary,
                                modifier = Modifier.size(28.dp)
                            )
                            Spacer(Modifier.width(10.dp))
                            Text(
                                "Admin Sign In",
                                style = MaterialTheme.typography.headlineSmall,
                                fontWeight = FontWeight.Bold
                            )
                        }

                        Spacer(Modifier.height(8.dp))
                        Text(
                            "Sign in with your blog credentials to publish posts from your mobile device, use Google Password Manager, or explore with the demo account.",
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            style = MaterialTheme.typography.bodyMedium
                        )

                        Spacer(Modifier.height(20.dp))

                        // Google Password Manager + Saved Vault Retrieve Button
                        Button(
                            onClick = {
                                coroutineScope.launch {
                                    var handledByGoogle = false
                                    val activity = context.findActivity()
                                    if (activity != null) {
                                        try {
                                            val getRequest = GetCredentialRequest(listOf(GetPasswordOption()))
                                            val result = credentialManager.getCredential(activity, getRequest)
                                            val credential = result.credential
                                            if (credential is PasswordCredential) {
                                                handledByGoogle = true
                                                username = credential.id
                                                password = credential.password
                                                pendingPasswordToSave = Pair(credential.id, credential.password)
                                                CredentialVault.saveCredential(context, credential.id, credential.password)
                                                savedVaultAccounts = CredentialVault.getSavedCredentials(context)
                                                viewModel.login(credential.id, credential.password)
                                            }
                                        } catch (e: GetCredentialException) {
                                            // Fall through to Encrypted CredentialVault if Google Play Services has no matching cert/domain entry
                                        } catch (e: Exception) {
                                            // Fall through to Encrypted CredentialVault
                                        }
                                    }

                                    if (!handledByGoogle) {
                                        val vaultAccounts = CredentialVault.getSavedCredentials(context)
                                        savedVaultAccounts = vaultAccounts
                                        if (vaultAccounts.size == 1) {
                                            val acc = vaultAccounts.first()
                                            username = acc.username
                                            password = acc.password
                                            pendingPasswordToSave = Pair(acc.username, acc.password)
                                            viewModel.login(acc.username, acc.password)
                                        } else if (vaultAccounts.size > 1) {
                                            showSavedCredentialsDialog = true
                                        } else {
                                            Toast.makeText(
                                                context,
                                                "No saved password found yet. Sign in once below and your password will be saved automatically!",
                                                Toast.LENGTH_LONG
                                            ).show()
                                        }
                                    }
                                }
                            },
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Icon(Icons.Default.Key, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(Modifier.width(8.dp))
                            Text(
                                if (savedVaultAccounts.isNotEmpty())
                                    "Use Google Passwords (${savedVaultAccounts.first().username})"
                                else
                                    "Use Google Passwords"
                            )
                        }

                        // Saved accounts quick chips when available
                        if (savedVaultAccounts.isNotEmpty()) {
                            Spacer(Modifier.height(10.dp))
                            FlowRow(
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                                verticalArrangement = Arrangement.spacedBy(6.dp),
                                modifier = Modifier.fillMaxWidth()
                            ) {
                                savedVaultAccounts.forEach { acc ->
                                    FilterChip(
                                        selected = username == acc.username && password == acc.password,
                                        onClick = {
                                            username = acc.username
                                            password = acc.password
                                            pendingPasswordToSave = Pair(acc.username, acc.password)
                                            viewModel.login(acc.username, acc.password)
                                        },
                                        leadingIcon = {
                                            Icon(
                                                Icons.Default.Key,
                                                contentDescription = null,
                                                tint = MaterialTheme.colorScheme.primary,
                                                modifier = Modifier.size(16.dp)
                                            )
                                        },
                                        label = { Text("Sign in as ${acc.username}") }
                                    )
                                }
                            }
                        }

                        Spacer(Modifier.height(16.dp))

                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Box(modifier = Modifier.weight(1f).height(1.dp).background(MaterialTheme.colorScheme.surfaceVariant))
                            Text(
                                "  or type credentials  ",
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            Box(modifier = Modifier.weight(1f).height(1.dp).background(MaterialTheme.colorScheme.surfaceVariant))
                        }

                        Spacer(Modifier.height(16.dp))

                        // Autofill-enabled Username
                        OutlinedTextField(
                            value = username,
                            onValueChange = { username = it },
                            label = { Text("Username") },
                            singleLine = true,
                            modifier = Modifier
                                .fillMaxWidth()
                                .onGloballyPositioned { usernameAutofillNode.boundingBox = it.boundsInWindow() }
                                .onFocusChanged { focusState ->
                                    autofill?.run {
                                        if (focusState.isFocused) {
                                            requestAutofillForNode(usernameAutofillNode)
                                        } else {
                                            cancelAutofillForNode(usernameAutofillNode)
                                        }
                                    }
                                },
                            shape = RoundedCornerShape(12.dp)
                        )

                        Spacer(Modifier.height(12.dp))

                        // Autofill-enabled Password with Show/Hide toggle
                        OutlinedTextField(
                            value = password,
                            onValueChange = { password = it },
                            label = { Text("Password") },
                            visualTransformation = if (passwordVisible) VisualTransformation.None else PasswordVisualTransformation(),
                            trailingIcon = {
                                IconButton(onClick = { passwordVisible = !passwordVisible }) {
                                    Icon(
                                        imageVector = if (passwordVisible) Icons.Default.VisibilityOff else Icons.Default.Visibility,
                                        contentDescription = if (passwordVisible) "Hide password" else "Show password",
                                        tint = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                            },
                            singleLine = true,
                            modifier = Modifier
                                .fillMaxWidth()
                                .onGloballyPositioned { passwordAutofillNode.boundingBox = it.boundsInWindow() }
                                .onFocusChanged { focusState ->
                                    autofill?.run {
                                        if (focusState.isFocused) {
                                            requestAutofillForNode(passwordAutofillNode)
                                        } else {
                                            cancelAutofillForNode(passwordAutofillNode)
                                        }
                                    }
                                },
                            shape = RoundedCornerShape(12.dp),
                            keyboardOptions = KeyboardOptions(
                                keyboardType = KeyboardType.Password,
                                imeAction = ImeAction.Done
                            )
                        )

                        Spacer(Modifier.height(20.dp))

                        Button(
                            onClick = {
                                val cleanUser = username.trim()
                                pendingPasswordToSave = Pair(cleanUser, password)
                                if (cleanUser.isNotBlank() && password.isNotBlank() && !cleanUser.equals("demo", ignoreCase = true)) {
                                    // Pre-save to encrypted vault on login attempt so even if the user navigates away immediately after login, it is stored
                                    CredentialVault.saveCredential(context, cleanUser, password)
                                    savedVaultAccounts = CredentialVault.getSavedCredentials(context)
                                }
                                viewModel.login(cleanUser, password)
                            },
                            enabled = !state.isLoading,
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            if (state.isLoading) {
                                CircularProgressIndicator(
                                    modifier = Modifier.size(20.dp),
                                    color = MaterialTheme.colorScheme.onPrimary,
                                    strokeWidth = 2.dp
                                )
                                Spacer(Modifier.width(8.dp))
                                Text("Signing in...")
                            } else {
                                Text("Sign In & Save Password")
                            }
                        }

                        Spacer(Modifier.height(12.dp))

                        OutlinedButton(
                            onClick = { viewModel.loginDemo() },
                            enabled = !state.isLoading,
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Text("Explore demo (demo / demo)")
                        }

                        state.error?.let {
                            Spacer(Modifier.height(12.dp))
                            Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
                        }
                    }
                }
            }
        }
    }

    // --- Saved Passwords Picker Dialog (when multiple accounts are saved) ---
    if (showSavedCredentialsDialog) {
        AlertDialog(
            onDismissRequest = { showSavedCredentialsDialog = false },
            title = {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        Icons.Default.Key,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(22.dp)
                    )
                    Spacer(Modifier.width(8.dp))
                    Text("Saved Passwords", fontWeight = FontWeight.Bold)
                }
            },
            text = {
                Column(
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    savedVaultAccounts.forEach { acc ->
                        Card(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable {
                                    username = acc.username
                                    password = acc.password
                                    pendingPasswordToSave = Pair(acc.username, acc.password)
                                    showSavedCredentialsDialog = false
                                    viewModel.login(acc.username, acc.password)
                                },
                            colors = CardDefaults.cardColors(
                                containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)
                            ),
                            shape = RoundedCornerShape(10.dp)
                        ) {
                            Row(
                                modifier = Modifier.padding(12.dp),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(acc.username, fontWeight = FontWeight.SemiBold)
                                    Text(
                                        "••••••••",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                                IconButton(
                                    onClick = {
                                        CredentialVault.removeCredential(context, acc.username)
                                        savedVaultAccounts = CredentialVault.getSavedCredentials(context)
                                        if (savedVaultAccounts.isEmpty()) {
                                            showSavedCredentialsDialog = false
                                        }
                                    }
                                ) {
                                    Icon(
                                        Icons.Default.Close,
                                        contentDescription = "Remove saved password",
                                        tint = MaterialTheme.colorScheme.onSurfaceVariant,
                                        modifier = Modifier.size(18.dp)
                                    )
                                }
                            }
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { showSavedCredentialsDialog = false }) {
                    Text("Close")
                }
            }
        )
    }

    // --- Article Picker Dialog (Shows all published articles to embed) ---
    if (showArticlePicker) {
        AlertDialog(
            onDismissRequest = { showArticlePicker = false },
            title = {
                Text("Attach Article", fontWeight = FontWeight.Bold)
            },
            text = {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(300.dp)
                        .verticalScroll(rememberScrollState())
                ) {
                    if (state.isLoadingArticles) {
                        Box(Modifier.fillMaxWidth().height(100.dp), contentAlignment = Alignment.Center) {
                            CircularProgressIndicator()
                        }
                    } else if (state.availableArticles.isEmpty()) {
                        Text(
                            "No published articles found.",
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            style = MaterialTheme.typography.bodyMedium,
                            modifier = Modifier.padding(16.dp)
                        )
                    } else {
                        state.availableArticles.forEach { article ->
                            Card(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = 4.dp)
                                    .clickable {
                                        viewModel.attachArticle(article.post_id)
                                        showArticlePicker = false
                                    },
                                colors = CardDefaults.cardColors(
                                    containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.4f)
                                ),
                                shape = RoundedCornerShape(8.dp)
                            ) {
                                Row(
                                    modifier = Modifier.padding(10.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    if (article.cover_image.isNotBlank()) {
                                        AsyncImage(
                                            model = article.cover_image,
                                            contentDescription = null,
                                            modifier = Modifier.size(36.dp).clip(RoundedCornerShape(6.dp)),
                                            contentScale = ContentScale.Crop
                                        )
                                        Spacer(Modifier.width(8.dp))
                                    }
                                    Column {
                                        Text(
                                            text = article.title.ifBlank { "Untitled Article" },
                                            style = MaterialTheme.typography.bodyMedium,
                                            fontWeight = FontWeight.SemiBold,
                                            maxLines = 1,
                                            overflow = TextOverflow.Ellipsis
                                        )
                                        Text(
                                            text = "/article/${article.post_id}",
                                            style = MaterialTheme.typography.labelSmall,
                                            color = MaterialTheme.colorScheme.primary
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { showArticlePicker = false }) {
                    Text("Close")
                }
            }
        )
    }

    // --- Post Picker Dialog ---
    if (showPostPicker) {
        AlertDialog(
            onDismissRequest = { showPostPicker = false },
            title = {
                Text("Attach Post", fontWeight = FontWeight.Bold)
            },
            text = {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(300.dp)
                        .verticalScroll(rememberScrollState())
                ) {
                    val postsList = state.availableArticles.filter { it.type == "post" }
                    if (postsList.isEmpty()) {
                        Text(
                            "Use '/post/<post_id>' in your text to embed another post.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(16.dp)
                        )
                    } else {
                        postsList.forEach { post ->
                            Card(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = 4.dp)
                                    .clickable {
                                        viewModel.attachPost(post.post_id)
                                        showPostPicker = false
                                    },
                                colors = CardDefaults.cardColors(
                                    containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.4f)
                                ),
                                shape = RoundedCornerShape(8.dp)
                            ) {
                                Column(modifier = Modifier.padding(10.dp)) {
                                    Text(
                                        text = post.title.ifBlank { post.content.take(60) },
                                        style = MaterialTheme.typography.bodyMedium,
                                        fontWeight = FontWeight.SemiBold,
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis
                                    )
                                    Text(
                                        text = "/post/${post.post_id}",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = MaterialTheme.colorScheme.primary
                                    )
                                }
                            }
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = { showPostPicker = false }) {
                    Text("Close")
                }
            }
        )
    }

    // --- Insert Block Modal Bottom Sheet (all 14 website rich blocks) ---
    if (showBlocksSheet) {
        ModalBottomSheet(
            onDismissRequest = { showBlocksSheet = false },
            sheetState = blocksSheetState
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 20.dp, vertical = 12.dp)
                    .verticalScroll(rememberScrollState())
            ) {
                Text(
                    "Insert Rich Block",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    "Choose a block to insert its syntax at your cursor.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Spacer(Modifier.height(14.dp))

                RICH_TEXT_BLOCKS.forEach { (label, snippet) ->
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 4.dp)
                            .clickable {
                                viewModel.appendSnippet(snippet)
                                showBlocksSheet = false
                            },
                        colors = CardDefaults.cardColors(
                            containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.4f)
                        ),
                        shape = RoundedCornerShape(10.dp)
                    ) {
                        Row(
                            modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text(label, fontWeight = FontWeight.Medium)
                            Text(
                                snippet.lines().first(),
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.primary,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis
                            )
                        }
                    }
                }
                Spacer(Modifier.height(24.dp))
            }
        }
    }
}
