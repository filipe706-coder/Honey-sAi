package pt.filipe.sussurros

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.launch

// A primeira fala da Inês. Tem de ser igual à SAUDACAO em personagem.py.
const val SAUDACAO =
    "*Levanta os olhos do livro quando a campainha da porta toca* " +
    "Ah, és tu outra vez. Já começava a achar que tinhas trocado esta " +
    "livraria por uma daquelas grandes do centro comercial. " +
    "*sorri* O que te traz cá hoje?"

// O ViewModel guarda o "estado" do chat: as mensagens, se a Inês está a
// escrever e se houve erro. O ecrã (ChatScreen) só desenha o que está aqui.
// Vantagem: se rodares o telemóvel, a conversa não se perde.
class ChatViewModel : ViewModel() {

    // mutableStateListOf: quando muda, o Compose redesenha o ecrã sozinho.
    val mensagens = mutableStateListOf(Mensagem("personagem", SAUDACAO))

    var aEscrever by mutableStateOf(false)
        private set

    var erro by mutableStateOf<String?>(null)
        private set

    fun enviar(texto: String) {
        val limpo = texto.trim()
        if (limpo.isEmpty() || aEscrever) return
        mensagens.add(Mensagem("utilizador", limpo))
        pedirResposta()
    }

    // Se falhou, volta a pedir a resposta para a mesma conversa.
    fun tentarDeNovo() = pedirResposta()

    private fun pedirResposta() {
        aEscrever = true
        erro = null
        // viewModelScope.launch corre isto em segundo plano.
        viewModelScope.launch {
            try {
                // Enviamos a conversa toda; o servidor escolhe as últimas 20.
                val r = Servidor.api.enviar(PedidoChat(mensagens.toList()))
                mensagens.add(Mensagem("personagem", r.resposta))
            } catch (e: Exception) {
                erro = "Não consegui falar com o servidor. Está ligado?"
            } finally {
                aEscrever = false
            }
        }
    }
}
