package pt.filipe.sussurros

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(vm: ChatViewModel = viewModel()) {
    var texto by remember { mutableStateOf("") }
    val lista = rememberLazyListState()

    // Sempre que chega uma mensagem nova, desce até ao fim da conversa.
    LaunchedEffect(vm.mensagens.size, vm.aEscrever) {
        val total = vm.mensagens.size + if (vm.aEscrever) 1 else 0
        if (total > 0) lista.animateScrollToItem(total - 1)
    }

    Scaffold(
        topBar = { TopAppBar(title = { Text("Inês") }) }
    ) { padding ->
        // imePadding: empurra tudo para cima quando o teclado abre.
        Column(Modifier.padding(padding).imePadding().fillMaxSize()) {

            LazyColumn(
                state = lista,
                modifier = Modifier.weight(1f).fillMaxWidth(),
                contentPadding = PaddingValues(12.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(vm.mensagens) { m -> Balao(m) }
                if (vm.aEscrever) {
                    item {
                        Text(
                            "Inês está a escrever…",
                            style = MaterialTheme.typography.bodySmall,
                            fontStyle = FontStyle.Italic
                        )
                    }
                }
            }

            // Se houve erro, mostra a mensagem e um botão para tentar de novo.
            vm.erro?.let { erro ->
                Row(
                    Modifier.fillMaxWidth().padding(horizontal = 12.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(erro, color = MaterialTheme.colorScheme.error, modifier = Modifier.weight(1f))
                    TextButton(onClick = { vm.tentarDeNovo() }) { Text("Tentar de novo") }
                }
            }

            // Caixa de texto + botão Enviar
            Row(
                Modifier.fillMaxWidth().padding(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                OutlinedTextField(
                    value = texto,
                    onValueChange = { texto = it },
                    placeholder = { Text("Escreve uma mensagem…") },
                    modifier = Modifier.weight(1f),
                    maxLines = 4
                )
                Spacer(Modifier.width(8.dp))
                Button(
                    onClick = { vm.enviar(texto); texto = "" },
                    enabled = texto.isNotBlank() && !vm.aEscrever
                ) { Text("Enviar") }
            }
        }
    }
}

// Um balão de conversa: à direita para ti, à esquerda para a Inês.
@Composable
fun Balao(m: Mensagem) {
    val minha = m.papel == "utilizador"
    Box(Modifier.fillMaxWidth(), contentAlignment = if (minha) Alignment.CenterEnd else Alignment.CenterStart) {
        Text(
            text = comItalicos(m.texto),
            color = if (minha) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier
                .widthIn(max = 300.dp)
                .background(
                    if (minha) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surfaceVariant,
                    RoundedCornerShape(16.dp)
                )
                .padding(horizontal = 14.dp, vertical = 10.dp)
        )
    }
}

// Transforma "*sorri*" em texto em itálico (sem os asteriscos).
// Percorre o texto e alterna entre normal e itálico a cada "*".
fun comItalicos(texto: String): AnnotatedString = buildAnnotatedString {
    texto.split("*").forEachIndexed { i, parte ->
        if (i % 2 == 1) withStyle(SpanStyle(fontStyle = FontStyle.Italic)) { append(parte) }
        else append(parte)
    }
}
