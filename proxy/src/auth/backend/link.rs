use crate::{auth, compute, stream::PqStream};
use tokio::io::{AsyncRead, AsyncWrite};
use utils::pq_proto::{BeMessage as Be, BeParameterStatusMessage};

fn hello_message(redirect_uri: &str, session_id: &str) -> String {
    format!(
        concat![
            "Welcome to Neon!\n",
            "Authenticate by visiting:\n",
            "    {redirect_uri}{session_id}\n\n",
        ],
        redirect_uri = redirect_uri,
        session_id = session_id,
    )
}

pub fn new_psql_session_id() -> String {
    hex::encode(rand::random::<[u8; 8]>())
}

pub async fn handle_user(
    redirect_uri: &reqwest::Url,
    client: &mut PqStream<impl AsyncRead + AsyncWrite + Unpin>,
) -> auth::Result<compute::NodeInfo> {
    let psql_session_id = new_psql_session_id();
    let greeting = hello_message(redirect_uri.as_str(), &psql_session_id);

    let db_info = super::with_waiter(psql_session_id, |waiter| async {
        // Give user a URL to spawn a new database
        client
            .write_message_noflush(&Be::AuthenticationOk)?
            .write_message_noflush(&BeParameterStatusMessage::encoding())?
            .write_message(&Be::NoticeResponse(&greeting))
            .await?;

        // Wait for web console response (see `mgmt`)
        waiter.await?.map_err(auth::AuthErrorImpl::auth_failed)
    })
    .await?;

    client.write_message_noflush(&Be::NoticeResponse("Connecting to database."))?;

    Ok(compute::NodeInfo {
        db_info,
        scram_keys: None,
    })
}
