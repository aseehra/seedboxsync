# frozen_string_literal: true
# typed: strict

require "sorbet-runtime"
require "daemons"
require "logger"
require "rb-inotify"

extend T::Sig # rubocop:disable Style/MixinUsage

if __FILE__ == $PROGRAM_NAME
  Daemons.run_proc("library-organizer", { log_output: true }) do
  end
end

# Holder of logic
class LibraryOrganizer
  extend T::Sig

  sig { params(library: Pathname, log_severity: Integer).void }
  def initialize(library, log_severity: Logger::Severity::DEBUG)
    @logger = T.let(Logger.new($stdout), Logger)
    @logger.level = log_severity
    @library = library
    @notifier = T.let(nil, T.nilable(INotify::Notifier))
  end

  sig { params(watch_dirs: T::Array[Pathname]).void }
  def watch(watch_dirs)
    @notifier&.close
    @notifier = T.let(INotify::Notifier.new, T.nilable(INotify::Notifier))
    notifier = T.must(@notifier)

    @logger.debug("watching watch_dirs=#{watch_dirs}")

    watch_dirs.each do |dir|
      notifier.watch(dir.to_s, :create, &method(:on_create))
    end
  end

  sig { void }
  def process
    @notifier&.process
  end

  sig { void }
  def run
    @notifier&.run
  end

  sig { params(path: Pathname).returns(T.nilable(Pathname)) }
  def series_name(path)
    normalized = path.basename.to_s.downcase

    series_name = case normalized
    when /(.*)\D(s\d+e\d+|\d+x\d+)/
      Regexp.last_match(1)&.gsub(".", " ")
    else
      @logger.warn("Could not parse series name: path=#{path}")
      return nil
    end

    @logger.debug("Parsed series name: path=#{path} series_name=#{series_name}")

    Pathname.new(series_name)
  end

  sig { params(event: INotify::Event).void }
  def on_create(event)
    path = Pathname.new(event.absolute_name)
    @logger.debug("on_create path=#{path}")

    series = series_name(path)
    return unless series

    if path.file?
      series_dir = @library / series
      series_dir.mkdir(0o770) unless series_dir.directory?
      (series_dir / path.basename).make_link(path)
    elsif path.directory?
      series_dir = @library / series
    end
  end
end
