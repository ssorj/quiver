#include <iostream>
#include <map>
#include <unistd.h>

#include <sys/types.h>

#include <proton/connection.hpp>
#include <proton/default_container.hpp>
#include <proton/delivery.hpp>
#include <proton/link.hpp>
#include <proton/messaging_handler.hpp>
#include <proton/tracker.hpp>
#include <proton/value.hpp>
#include <proton/receiver_options.hpp>




class simple_peer : public proton::messaging_handler 
{
  private:

    std::string output_dir;
    std::string mode;
    std::string operation;
    std::string url;
    proton::sender sender;
    proton::receiver receiver;
    int sent;
    int confirmed;
    int expected;
    int received;
    int n_bytes;
    int credit;
    std::string message_body;


  public:
    simple_peer ( const std::string & _output_dir,
                  const std::string & _mode, 
                  const std::string & _operation,
                  const std::string & _url, 
                  int n_messages, 
                  int _n_bytes,
                  int _credit
                ) :
        output_dir ( _output_dir ),
        mode ( _mode ),
        operation ( _operation ),
        url ( _url ), 
        sent ( 0 ), 
        confirmed ( 0 ), 
        expected ( n_messages ), 
        received ( 0 ), 
        n_bytes ( _n_bytes ),
        credit  ( _credit ),
        message_body ( n_bytes, 'x' )
    {
    }



    void 
    on_container_start ( proton::container & c ) override 
    {
      proton::connection_options co;

      if ( operation == "send" )
      {
        sender = c.open_sender ( url );
      }
      else
      if ( operation == "receive" )
      {
        receiver = c.open_receiver ( url, proton::receiver_options().handler(*this).credit_window(credit) );
      }
    }



    void 
    on_sendable ( proton::sender & s ) override 
    {
      if ( operation == "send" )
      {
        while ( s.credit() && sent < expected ) 
        {
          proton::message msg;
          msg.id ( sent + 1 );
          msg.body ( message_body );

          s.send ( msg );
          sent++;
        }
      }
    }



    void 
    on_tracker_accept ( proton::tracker & t ) override 
    {
      if ( operation == "receive" )
      {
        confirmed ++;

        if ( confirmed >= expected ) 
        {
          t.connection().close();
        }
      }
    }



    void 
    on_transport_close ( proton::transport & ) override 
    {
      if ( operation == "send" )
      {
        sent = confirmed;
      }
    }



    void 
    on_message ( proton::delivery & d, proton::message & msg ) override 
    {
      if ( operation == "receive" )
      {
        if ( expected == 0 || received < expected ) 
        {
          received++;

          if ( received >= expected ) 
          {
            d.receiver().close();
            d.connection().close();
          }
        }
      }
    }

};





int 
main ( int argc, char ** argv ) 
{
  std::string output_dir = argv[1];
  std::string mode       = argv[2];
  std::string operation  = argv[3];
  std::string host       = argv[4];
  std::string port       = argv[5];
  std::string path       = argv[6];
  int         n_messages = std::atoi(argv[7]);
  int         n_bytes    = std::atoi(argv[8]);
  int         credit     = std::atoi(argv[9]);

  if ( mode != "client" )
  {
    std::cerr << "quiver: error: I have not yet implemented non-client mode." 
              << std::endl;
    return 1;
  }

  if ( port == "-") 
  {
    port = "5672";
  }

  simple_peer send ( output_dir,
                     mode,
                     operation,
                     host + ":" + port + "/" + path, 
                     n_messages, 
                     n_bytes,
                     credit
                   );

  try 
  {
    proton::default_container ( send ).run();
  }
  catch ( const std::exception & e )
  {
    std::cerr << e.what() << std::endl;
    return 1;
  }

  return 0;
}





